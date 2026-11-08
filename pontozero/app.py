"""Interface do Ponto Zero."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import APP_NAME, VERSION
from .crosshair import (BUILTIN_PRESETS, LIMITS, STYLE_LABELS, STYLES, Crosshair, from_share_code, render,
                        to_share_code)
from .fivem import to_crosshair as fivem_to_crosshair
from .overlay import HOTKEYS, Overlay, already_running, enable_dpi_awareness, key_down, screen_size
from .storage import Store, data_dir, export_presets, import_presets, unique_name

# --------------------------------------------------------------------------- identidade visual
BG = "#0B0D12"
SIDEBAR = "#0F1218"
CARD = "#151922"
CARD_2 = "#1C212C"
BORDER = "#252B38"
TEXT = "#E8ECF4"
MUTED = "#8A93A6"
ACCENT = "#3DF5A7"
ACCENT_HOVER = "#2AD991"
ACCENT_DIM = "#123A2B"
ACCENT_TEXT = "#04140C"
DANGER = "#FF5C6C"
FONT = "Segoe UI"
PALETTE = ["#FFFFFF", "#000000", "#3DF5A7", "#FACC15", "#FF8A00",
           "#FF4D6D", "#FF4DD8", "#A855F7", "#3B82F6", "#22D3EE"]
PREVIEW_W, PREVIEW_H = 420, 232
ZOOMS = {"1x": 1, "2x": 2, "4x": 4}
BACKGROUNDS = ("Cena", "Escuro", "Claro")


def resource(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / rel


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def make_background(mode: str, width: int, height: int) -> Image.Image:
    if mode == "Escuro":
        return Image.new("RGB", (width, height), (21, 24, 31))
    if mode == "Claro":
        return Image.new("RGB", (width, height), (233, 237, 242))
    # Cena genérica de rua: céu, chão e prédios, para conferir o contraste da mira.
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    horizon = int(height * 0.62)

    def lerp(a, b, t):
        return tuple(int(x + (y - x) * t) for x, y in zip(a, b))

    for y in range(height):
        if y < horizon:
            color = lerp((70, 116, 168), (214, 196, 160), y / horizon)
        else:
            color = lerp((118, 97, 72), (52, 43, 34), (y - horizon) / (height - horizon))
        d.line([(0, y), (width, y)], fill=color)
    for x, wf, hf, col in ((0.0, 0.17, 0.30, (148, 126, 98)), (0.17, 0.11, 0.44, (171, 147, 113)),
                           (0.64, 0.14, 0.38, (138, 118, 93)), (0.78, 0.22, 0.27, (160, 137, 107))):
        d.rectangle([x * width, horizon - hf * height, (x + wf) * width, horizon], fill=col)
    d.rectangle([0.38 * width, horizon - 0.25 * height, 0.62 * width, horizon], fill=(126, 104, 80))
    d.rectangle([0.46 * width, horizon - 0.15 * height, 0.54 * width, horizon], fill=(58, 46, 36))
    return img


# --------------------------------------------------------------------------- controles
class SliderRow(ctk.CTkFrame):
    def __init__(self, master, app: "App", label: str, key: str, unit: str = "px") -> None:
        super().__init__(master, fg_color="transparent")
        self.app, self.key, self.unit = app, key, unit
        self.lo, self.hi = LIMITS[key]
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, font=font(13), text_color=TEXT).grid(row=0, column=0, columnspan=2, sticky="w")
        self.badge = ctk.CTkLabel(self, text="", width=58, height=24, fg_color=CARD_2, corner_radius=6,
                                  font=font(12, "bold"), text_color=TEXT)
        self.badge.grid(row=0, column=2, columnspan=2, sticky="e")
        step = dict(width=26, height=24, corner_radius=6, fg_color=CARD_2, hover_color=BORDER,
                    text_color=TEXT, font=font(14, "bold"))
        ctk.CTkButton(self, text="−", command=lambda: self.nudge(-1), **step).grid(row=1, column=0, pady=(4, 0))
        self.slider = ctk.CTkSlider(self, from_=self.lo, to=self.hi, number_of_steps=self.hi - self.lo,
                                    command=lambda v: self.set(round(v)), button_color=ACCENT,
                                    button_hover_color=ACCENT_HOVER, progress_color=ACCENT, fg_color=BORDER)
        self.slider.grid(row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=(4, 0))
        ctk.CTkButton(self, text="+", command=lambda: self.nudge(1), **step).grid(row=1, column=3, pady=(4, 0))

    def nudge(self, delta: int) -> None:
        self.set(getattr(self.app.cfg, self.key) + delta)

    def set(self, value: int) -> None:
        value = max(self.lo, min(self.hi, int(value)))
        self.show(value)
        if value != getattr(self.app.cfg, self.key):
            self.app.update_cfg(**{self.key: value})

    def show(self, value: int) -> None:
        self.slider.set(value)
        self.badge.configure(text=f"{value}{self.unit}")

    def sync(self, cfg: Crosshair) -> None:
        self.show(getattr(cfg, self.key))


class ColorRow(ctk.CTkFrame):
    def __init__(self, master, app: "App", label: str, key: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.app, self.key = app, key
        ctk.CTkLabel(self, text=label, font=font(13), text_color=TEXT).pack(anchor="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", pady=(6, 0), fill="x")
        self.swatches = {}
        for color in PALETTE:
            b = ctk.CTkButton(row, text="", width=24, height=24, corner_radius=12, fg_color=color,
                              hover_color=color, border_width=2, border_color=CARD,
                              command=lambda c=color: self.choose(c))
            b.pack(side="left", padx=(0, 6))
            self.swatches[color] = b
        ctk.CTkButton(row, text="+", width=24, height=24, corner_radius=12, fg_color=CARD_2, hover_color=BORDER,
                      text_color=TEXT, font=font(14, "bold"), command=self.pick).pack(side="left", padx=(0, 10))
        self.entry = ctk.CTkEntry(row, width=86, height=26, font=font(12), fg_color=CARD_2, border_color=BORDER,
                                  text_color=TEXT)
        self.entry.pack(side="left")
        self.entry.bind("<Return>", lambda _e: self.choose(self.entry.get()))
        self.entry.bind("<FocusOut>", lambda _e: self.choose(self.entry.get()))

    def pick(self) -> None:
        _rgb, hex_color = colorchooser.askcolor(color=getattr(self.app.cfg, self.key), title="Escolher cor")
        if hex_color:
            self.choose(hex_color)

    def choose(self, color: str) -> None:
        color = color.strip()
        if not color.startswith("#"):
            color = "#" + color
        updated = self.app.cfg.copy(**{self.key: color})
        if getattr(updated, self.key) != color.upper():  # hex inválido: from_dict manteve a cor anterior
            self.sync(self.app.cfg)
            return
        self.app.update_cfg(**{self.key: color.upper()})

    def sync(self, cfg: Crosshair) -> None:
        current = getattr(cfg, self.key)
        for color, button in self.swatches.items():
            selected = color == current
            button.configure(border_color=(ACCENT if color == "#FFFFFF" else "#FFFFFF") if selected else CARD)
        self.entry.delete(0, "end")
        self.entry.insert(0, current)


class Switch(ctk.CTkSwitch):
    def __init__(self, master, app: "App", label: str, key: str) -> None:
        self.app, self.key = app, key
        super().__init__(master, text=label, font=font(13), text_color=TEXT, progress_color=ACCENT,
                         button_color=TEXT, button_hover_color="#FFFFFF", fg_color=BORDER,
                         command=lambda: app.update_cfg(**{key: bool(self.get())}))

    def sync(self, cfg: Crosshair) -> None:
        self.select() if getattr(cfg, self.key) else self.deselect()


class TextDialog(ctk.CTkToplevel):
    """Diálogo com caixa de texto de várias linhas (o CTkInputDialog só aceita uma linha)."""

    def __init__(self, master, title: str, prompt: str) -> None:
        super().__init__(master, fg_color=BG)
        self.title(title)
        self.geometry("560x340")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        ctk.CTkLabel(self, text=prompt, font=font(13), text_color=TEXT, justify="left").pack(anchor="w", padx=18,
                                                                                         pady=(16, 8))
        self.box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), fg_color=CARD,
                                  border_color=BORDER, border_width=1, text_color=TEXT, wrap="char")
        self.box.pack(fill="both", expand=True, padx=18)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=14)
        ctk.CTkButton(row, text="Importar", height=36, corner_radius=8, font=font(13, "bold"), fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, text_color=ACCENT_TEXT, command=self._ok).pack(side="right")
        ctk.CTkButton(row, text="Cancelar", height=36, corner_radius=8, font=font(13), fg_color=CARD,
                      hover_color=CARD_2, border_width=1, border_color=BORDER, text_color=TEXT,
                      command=self.destroy).pack(side="right", padx=(0, 8))
        self.after(100, self._focus)

    def _focus(self) -> None:
        self.lift()
        self.grab_set()
        self.box.focus_set()

    def _ok(self) -> None:
        self.result = self.box.get("1.0", "end").strip()
        self.destroy()

    def get(self) -> str | None:
        self.wait_window()
        return self.result


# --------------------------------------------------------------------------- aplicativo
class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=BG)
        self.title(f"{APP_NAME} — mira fixa")
        self.geometry("1100x720")
        self.minsize(1020, 680)
        icon = resource("assets/icon.ico")
        if icon.exists():
            self.iconbitmap(icon)
            self.after(300, lambda: self.iconbitmap(icon))  # o CTk troca o ícone ~200 ms depois de abrir

        self.store = Store()
        self.cfg = self.store.current
        self.active = False
        self.controls = []
        self.zoom = 2
        self.background = "Cena"
        self._bg_cache = {}
        self._save_job = None
        self._key_was_down = False

        try:
            self.overlay = Overlay()
        except OSError as exc:
            self.overlay = None
            messagebox.showerror(APP_NAME, f"Não foi possível criar o overlay da mira:\n{exc}")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self.pages = {"editor": self._build_editor(), "presets": self._build_presets(),
                      "settings": self._build_settings()}
        self.show_page("editor")
        self.sync_all()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(40, self._poll_hotkey)
        self.after(1000, self._keep_on_top)
        if self.store.settings["start_active"]:
            self.set_active(True)

    # ---------------------------------------------------------------- estrutura
    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=220)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.columnconfigure(0, weight=1)
        bar.rowconfigure(5, weight=1)

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=20, pady=(24, 26), sticky="w")
        logo = render(Crosshair(style="circle", size=11, thickness=2, center_dot=True, dot_size=4,
                                color=ACCENT, outline=False))
        ctk.CTkLabel(brand, text="", image=ctk.CTkImage(logo, size=logo.size)).grid(row=0, column=0, rowspan=2,
                                                                                    padx=(0, 10))
        ctk.CTkLabel(brand, text="PONTO ZERO", font=font(17, "bold"), text_color=TEXT).grid(row=0, column=1,
                                                                                          sticky="sw")
        ctk.CTkLabel(brand, text="MIRA FIXA", font=font(10, "bold"), text_color=ACCENT).grid(row=1, column=1,
                                                                                           sticky="nw")

        self.nav = {}
        for row, (key, label) in enumerate((("editor", "Editor de mira"), ("presets", "Minhas miras"),
                                             ("settings", "Configurações")), start=1):
            b = ctk.CTkButton(bar, text=label, anchor="w", height=40, corner_radius=8, font=font(14),
                              fg_color="transparent", hover_color=CARD_2, text_color=MUTED,
                              border_width=1, border_color=SIDEBAR, command=lambda k=key: self.show_page(k))
            b.grid(row=row, column=0, padx=14, pady=3, sticky="ew")
            self.nav[key] = b

        status = ctk.CTkFrame(bar, fg_color=CARD, corner_radius=10, border_width=1, border_color=BORDER)
        status.grid(row=6, column=0, padx=14, pady=(0, 10), sticky="ew")
        self.status_dot = ctk.CTkLabel(status, text="●", font=font(16), text_color=MUTED)
        self.status_dot.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=10)
        self.status_text = ctk.CTkLabel(status, text="", font=font(13, "bold"), text_color=TEXT)
        self.status_text.grid(row=0, column=1, sticky="sw", pady=(10, 0))
        self.status_hint = ctk.CTkLabel(status, text="", font=font(11), text_color=MUTED)
        self.status_hint.grid(row=1, column=1, sticky="nw", pady=(0, 10))
        ctk.CTkLabel(bar, text=f"{APP_NAME.upper()}  ·  v{VERSION}", font=font(10), text_color=MUTED).grid(
            row=7, column=0, padx=20, pady=(0, 14), sticky="w")

    def _page(self, title: str, subtitle: str) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        page.columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text=title, font=font(22, "bold"), text_color=TEXT).grid(row=0, column=0, padx=28,
                                                                                  pady=(22, 0), sticky="w")
        ctk.CTkLabel(page, text=subtitle, font=font(13), text_color=MUTED).grid(row=1, column=0, padx=28,
                                                                              pady=(0, 14), sticky="w")
        return page

    def _card(self, master) -> ctk.CTkFrame:
        return ctk.CTkFrame(master, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)

    def _build_editor(self) -> ctk.CTkFrame:
        page = self._page("Editor de mira", "Ajuste cada detalhe. A mira no jogo muda na hora.")
        page.rowconfigure(2, weight=1)
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=2, column=0, padx=28, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Pré-visualização
        left = self._card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ctk.CTkLabel(left, text="PRÉ-VISUALIZAÇÃO", font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(14, 8))
        self.preview = ctk.CTkLabel(left, text="", width=PREVIEW_W, height=PREVIEW_H, fg_color=BG, corner_radius=8)
        self.preview.pack(padx=16)
        opts = ctk.CTkFrame(left, fg_color="transparent")
        opts.pack(fill="x", padx=16, pady=14)
        seg = dict(font=font(12), selected_color=ACCENT_DIM, selected_hover_color=ACCENT_DIM,
                   unselected_color=CARD_2, unselected_hover_color=BORDER, fg_color=CARD_2, text_color=TEXT)
        zoom = ctk.CTkSegmentedButton(opts, values=list(ZOOMS), command=self._set_zoom, **seg)
        zoom.set("2x")
        zoom.pack(side="left")
        bg = ctk.CTkSegmentedButton(opts, values=list(BACKGROUNDS), command=self._set_background, **seg)
        bg.set(self.background)
        bg.pack(side="right")
        ctk.CTkLabel(left, text="1x mostra o tamanho real que aparece no jogo.", font=font(11),
                     text_color=MUTED).pack(anchor="w", padx=16, pady=(0, 10))
        colors = ctk.CTkFrame(left, fg_color="transparent")
        colors.pack(fill="x", padx=8)
        self._add(ColorRow(colors, self, "Cor da mira", "color"), pady=(0, 12))
        self._add(SliderRow(colors, self, "Opacidade", "opacity", unit="%"))

        # Abas de ajuste
        tabs = ctk.CTkTabview(body, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER,
                              segmented_button_fg_color=CARD_2, segmented_button_selected_color=ACCENT_DIM,
                              segmented_button_selected_hover_color=ACCENT_DIM,
                              segmented_button_unselected_color=CARD_2,
                              segmented_button_unselected_hover_color=BORDER, text_color=TEXT)
        tabs.grid(row=0, column=1, sticky="nsew")
        tabs._segmented_button.configure(font=font(13))
        for name in ("Estilo", "Contorno", "Posição"):
            tabs.add(name)
        self._build_style_tab(tabs.tab("Estilo"))
        self._build_outline_tab(tabs.tab("Contorno"))
        self._build_position_tab(tabs.tab("Posição"))

        # Ações
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.grid(row=3, column=0, padx=28, pady=18, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.toggle_btn = ctk.CTkButton(actions, text="", height=46, corner_radius=10, font=font(15, "bold"),
                                        command=lambda: self.set_active(not self.active))
        self.toggle_btn.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        if self.overlay is None:
            self.toggle_btn.configure(state="disabled")
        secondary = dict(height=46, corner_radius=10, font=font(13), fg_color=CARD, hover_color=CARD_2,
                         border_width=1, border_color=BORDER, text_color=TEXT, width=130)
        for col, (label, cmd) in enumerate((("Redefinir", self.reset), ("Salvar preset", self.save_preset),
                                            ("Copiar código", lambda: self.copy_code(self.cfg)),
                                            ("Exportar", self.export_current)), start=1):
            ctk.CTkButton(actions, text=label, command=cmd, **secondary).grid(row=0, column=col, padx=(0, 10))
        return page

    def _tab_body(self, tab) -> ctk.CTkFrame:
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent", scrollbar_button_color=BORDER)
        frame.pack(fill="both", expand=True)
        return frame

    def _add(self, control, pady=(0, 14)):
        control.pack(fill="x", padx=8, pady=pady)
        self.controls.append(control)
        return control

    def _build_style_tab(self, tab) -> None:
        body = self._tab_body(tab)
        ctk.CTkLabel(body, text="Estilo da mira", font=font(13), text_color=TEXT).pack(anchor="w", padx=8)
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(6, 16))
        grid.columnconfigure((0, 1, 2), weight=1)
        self.style_buttons = {}
        for i, style in enumerate(STYLES):
            sample = Crosshair(style=style, size=6 if style == "dot" else 7, thickness=2, gap=3,
                               center_dot=style == "circle", dot_size=2, color=TEXT, outline=False)
            if style == "corners":
                sample = sample.copy(size=4, gap=3)
            icon = render(sample)
            b = ctk.CTkButton(grid, text=STYLE_LABELS[style], image=ctk.CTkImage(icon, size=icon.size),
                              compound="top", width=80, height=62, corner_radius=10, font=font(12),
                              fg_color=CARD_2, hover_color=BORDER, text_color=TEXT, border_width=2,
                              border_color=CARD_2, command=lambda s=style: self.update_cfg(style=s))
            b.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            self.style_buttons[style] = b
        self._add(SliderRow(body, self, "Tamanho", "size"))
        self._add(SliderRow(body, self, "Espessura", "thickness"))
        self._add(SliderRow(body, self, "Espaçamento", "gap"))
        self._add(Switch(body, self, "Ponto central", "center_dot"))
        self._add(SliderRow(body, self, "Tamanho do ponto central", "dot_size"))
        self._add(Switch(body, self, "Ponto quadrado (como o do FiveM/CS:GO)", "square_dot"))
        self._add(Switch(body, self, "Estilo T (cruz sem a linha de cima)", "t_style"))

    def _build_outline_tab(self, tab) -> None:
        body = self._tab_body(tab)
        self._add(Switch(body, self, "Contorno (melhora a leitura em fundo claro)", "outline"), pady=(0, 16))
        self._add(SliderRow(body, self, "Espessura do contorno", "outline_thickness"))
        self._add(ColorRow(body, self, "Cor do contorno", "outline_color"), pady=(0, 18))
        self._add(SliderRow(body, self, "Opacidade do contorno", "outline_opacity", unit="%"))

    def _build_position_tab(self, tab) -> None:
        body = self._tab_body(tab)
        ctk.CTkLabel(body, text="A mira fica no centro da tela principal. Desloque só se o centro do\n"
                                "jogo não bater com o da tela (ex.: jogo em janela).",
                     font=font(12), text_color=MUTED, justify="left").pack(anchor="w", padx=8, pady=(0, 14))
        self._add(SliderRow(body, self, "Deslocamento horizontal", "offset_x"))
        self._add(SliderRow(body, self, "Deslocamento vertical", "offset_y"))
        ctk.CTkButton(body, text="Centralizar", height=34, corner_radius=8, font=font(13), fg_color=CARD_2,
                      hover_color=BORDER, text_color=TEXT,
                      command=lambda: self.update_cfg(offset_x=0, offset_y=0)).pack(anchor="w", padx=8)

    def _build_presets(self) -> ctk.CTkFrame:
        page = self._page("Minhas miras", "Seus presets e os que vêm com o programa. Importe, exporte e compartilhe.")
        page.rowconfigure(3, weight=1)
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=2, column=0, padx=28, pady=(0, 12), sticky="w")
        primary = dict(height=38, corner_radius=8, font=font(13, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       text_color=ACCENT_TEXT)
        secondary = dict(height=38, corner_radius=8, font=font(13), fg_color=CARD, hover_color=CARD_2,
                         border_width=1, border_color=BORDER, text_color=TEXT)
        ctk.CTkButton(bar, text="Importar do FiveM (F8)", command=self.import_fivem, **primary).pack(side="left",
                                                                                                padx=(0, 8))
        ctk.CTkButton(bar, text="Importar arquivo", command=self.import_file, **secondary).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Colar código", command=self.paste_code, **secondary).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exportar todas", command=self.export_all, **secondary).pack(side="left")
        self.preset_list = ctk.CTkScrollableFrame(page, fg_color="transparent", scrollbar_button_color=BORDER)
        self.preset_list.grid(row=3, column=0, padx=20, pady=(0, 18), sticky="nsew")
        self.preset_list.columnconfigure(0, weight=1)
        return page

    def refresh_presets(self) -> None:
        for child in self.preset_list.winfo_children():
            child.destroy()
        entries = [(n, c, True) for n, c in BUILTIN_PRESETS.items()] + \
                  [(n, c, False) for n, c in sorted(self.store.presets.items(), key=lambda kv: kv[0].lower())]
        small = dict(height=32, corner_radius=8, font=font(12), fg_color=CARD_2, hover_color=BORDER,
                     text_color=TEXT, width=96)
        for row, (name, cfg, builtin) in enumerate(entries):
            card = self._card(self.preset_list)
            card.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            card.columnconfigure(1, weight=1)
            thumb = Image.new("RGBA", (44, 44), (21, 24, 31, 255))
            icon = render(cfg)
            if icon.size[0] > 44:
                icon = icon.resize((44, 44), Image.LANCZOS)
            thumb.paste(icon, ((44 - icon.size[0]) // 2, (44 - icon.size[1]) // 2), icon)
            ctk.CTkLabel(card, text="", image=ctk.CTkImage(thumb, size=(44, 44))).grid(row=0, column=0, rowspan=2,
                                                                                      padx=12, pady=10)
            ctk.CTkLabel(card, text=name, font=font(14, "bold"), text_color=TEXT).grid(row=0, column=1, sticky="sw")
            ctk.CTkLabel(card, text=("Padrão do programa  ·  " if builtin else "") + STYLE_LABELS[cfg.style],
                         font=font(11), text_color=MUTED).grid(row=1, column=1, sticky="nw")
            ctk.CTkButton(card, text="Usar", command=lambda c=cfg: self.use_preset(c),
                          **{**small, "fg_color": ACCENT, "hover_color": ACCENT_HOVER, "text_color": ACCENT_TEXT,
                             "font": font(12, "bold")}).grid(row=0, column=2, rowspan=2, padx=(0, 6))
            ctk.CTkButton(card, text="Copiar código", command=lambda c=cfg: self.copy_code(c), **small).grid(
                row=0, column=3, rowspan=2, padx=(0, 6))
            ctk.CTkButton(card, text="Exportar", command=lambda n=name, c=cfg: self.export_one(n, c), **small).grid(
                row=0, column=4, rowspan=2, padx=(0, 6))
            if not builtin:
                ctk.CTkButton(card, text="Excluir", command=lambda n=name: self.delete_preset(n),
                              **{**small, "text_color": DANGER}).grid(row=0, column=5, rowspan=2, padx=(0, 12))
            else:
                ctk.CTkLabel(card, text="", width=96).grid(row=0, column=5, rowspan=2, padx=(0, 12))

    def _build_settings(self) -> ctk.CTkFrame:
        page = self._page("Configurações", "Atalho, inicialização e dicas para o FiveM.")
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=2, column=0, padx=28, sticky="new")
        body.columnconfigure(0, weight=1)

        card = self._card(body)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        card.columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Atalho para ligar/desligar a mira", font=font(14, "bold"),
                     text_color=TEXT).grid(row=0, column=0, padx=18, pady=(16, 0), sticky="w")
        ctk.CTkLabel(card, text="Funciona mesmo com o jogo em foco. Evite F8 (console do FiveM).",
                     font=font(12), text_color=MUTED).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")
        hotkey = ctk.CTkOptionMenu(card, values=list(HOTKEYS), command=self.set_hotkey, width=150, font=font(13),
                                   fg_color=CARD_2, button_color=BORDER, button_hover_color=ACCENT_DIM,
                                   text_color=TEXT, dropdown_fg_color=CARD_2, dropdown_text_color=TEXT,
                                   dropdown_hover_color=ACCENT_DIM)
        hotkey.set(self.store.settings["hotkey"] if self.store.settings["hotkey"] in HOTKEYS else "F9")
        hotkey.grid(row=0, column=1, rowspan=2, padx=18)

        card2 = self._card(body)
        card2.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        start = ctk.CTkSwitch(card2, text="Ligar a mira automaticamente ao abrir o programa", font=font(14),
                              text_color=TEXT, progress_color=ACCENT, fg_color=BORDER, button_color=TEXT,
                              command=lambda: self._set_setting("start_active", bool(start.get())))
        if self.store.settings["start_active"]:
            start.select()
        start.pack(anchor="w", padx=18, pady=18)

        tip = ctk.CTkFrame(body, fg_color=ACCENT_DIM, corner_radius=12)
        tip.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(tip, text="A mira não aparece no jogo?", font=font(14, "bold"), text_color=ACCENT).pack(
            anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(tip, justify="left", font=font(13), text_color=TEXT, text=(
            "No FiveM, abra Configurações → Gráficos e mude o Modo de exibição para\n"
            "\"Janela sem bordas\" (Borderless). Em tela cheia exclusiva o Windows não deixa\n"
            "nenhum programa desenhar por cima do jogo.\n\n"
            "O Ponto Zero só desenha uma imagem no centro da tela: não lê nem altera o jogo.\n"
            "Mesmo assim, confira as regras do servidor em que você joga.")).pack(anchor="w", padx=18,
                                                                                  pady=(0, 16))

        ctk.CTkButton(body, text="Abrir pasta de dados", height=36, corner_radius=8, font=font(13),
                      fg_color=CARD, hover_color=CARD_2, border_width=1, border_color=BORDER, text_color=TEXT,
                      command=lambda: os.startfile(data_dir())).grid(row=3, column=0, sticky="w")
        return page

    # ---------------------------------------------------------------- estado
    def show_page(self, key: str) -> None:
        for name, page in self.pages.items():
            page.grid_forget()
            self.nav[name].configure(fg_color="transparent", text_color=MUTED, border_color=SIDEBAR)
        self.pages[key].grid(row=0, column=1, sticky="nsew")
        self.nav[key].configure(fg_color=ACCENT_DIM, text_color=ACCENT, border_color=ACCENT_DIM)
        if key == "presets":
            self.refresh_presets()

    def update_cfg(self, **changes) -> None:
        self.cfg = self.cfg.copy(**changes)
        self.sync_all()

    def sync_all(self) -> None:
        for control in self.controls:
            control.sync(self.cfg)
        for style, button in self.style_buttons.items():
            selected = style == self.cfg.style
            button.configure(border_color=ACCENT if selected else CARD_2,
                             fg_color=ACCENT_DIM if selected else CARD_2)
        self.draw_preview()
        if self.active:
            self.overlay.draw(render(self.cfg), self.cfg.offset_x, self.cfg.offset_y)
        self._update_status()
        self.store.current = self.cfg
        self._schedule_save()

    def draw_preview(self) -> None:
        scale = self.preview._get_widget_scaling()
        width, height = int(PREVIEW_W * scale), int(PREVIEW_H * scale)
        key = (self.background, width, height)
        if key not in self._bg_cache:
            self._bg_cache[key] = make_background(self.background, width, height)
        img = self._bg_cache[key].copy()
        cross = render(self.cfg)
        if self.zoom > 1:
            cross = cross.resize((cross.size[0] * self.zoom, cross.size[1] * self.zoom), Image.NEAREST)
        x = width // 2 - cross.size[0] // 2 + self.cfg.offset_x * self.zoom
        y = height // 2 - cross.size[1] // 2 + self.cfg.offset_y * self.zoom
        img.paste(cross, (x, y), cross)
        # Imagem já no tamanho físico: o CTk não reamostra, e 1x continua sendo 1 pixel de tela.
        self.preview.configure(image=ctk.CTkImage(img, size=(PREVIEW_W, PREVIEW_H)))

    def _set_zoom(self, value: str) -> None:
        self.zoom = ZOOMS[value]
        self.draw_preview()

    def _set_background(self, value: str) -> None:
        self.background = value
        self.draw_preview()

    def set_active(self, active: bool) -> None:
        if self.overlay is None:
            return
        self.active = active
        if active:
            self.overlay.draw(render(self.cfg), self.cfg.offset_x, self.cfg.offset_y)
            self.overlay.show()
        else:
            self.overlay.hide()
        self._update_status()

    def _update_status(self) -> None:
        key = self.store.settings["hotkey"]
        if self.active:
            self.toggle_btn.configure(text=f"DESATIVAR MIRA   ·   {key}", fg_color=CARD_2, hover_color=BORDER,
                                      text_color=DANGER, border_width=1, border_color=DANGER)
            self.status_dot.configure(text_color=ACCENT)
            self.status_text.configure(text="Mira ativa")
        else:
            self.toggle_btn.configure(text=f"ATIVAR MIRA   ·   {key}", fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                      text_color=ACCENT_TEXT, border_width=0)
            self.status_dot.configure(text_color=MUTED)
            self.status_text.configure(text="Mira desligada")
        self.status_hint.configure(text=f"Atalho: {key}")

    def _schedule_save(self) -> None:
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(600, self._save)

    def _save(self) -> None:
        self._save_job = None
        try:
            self.store.save()
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível salvar as configurações:\n{exc}")

    def _set_setting(self, key: str, value) -> None:
        self.store.settings[key] = value
        self._schedule_save()

    def set_hotkey(self, key: str) -> None:
        self._set_setting("hotkey", key)
        self._update_status()

    def _poll_hotkey(self) -> None:
        vk = HOTKEYS.get(self.store.settings["hotkey"], HOTKEYS["F9"])
        down = key_down(vk)
        if down and not self._key_was_down:
            self.set_active(not self.active)
        self._key_was_down = down
        self.after(40, self._poll_hotkey)

    def _keep_on_top(self) -> None:
        if self.overlay:
            self.overlay.raise_to_top()
        self.after(1000, self._keep_on_top)

    # ---------------------------------------------------------------- ações
    def reset(self) -> None:
        self.cfg = Crosshair()
        self.sync_all()

    def use_preset(self, cfg: Crosshair) -> None:
        self.cfg = cfg.copy()
        self.sync_all()
        self.show_page("editor")

    def save_preset(self) -> None:
        name = ctk.CTkInputDialog(title="Salvar preset", text="Nome do preset:").get_input()
        if name is None or not name.strip():
            return
        name = name.strip()[:40]
        if name in BUILTIN_PRESETS:
            name = unique_name(name, set(BUILTIN_PRESETS) | set(self.store.presets))
        elif name in self.store.presets and not messagebox.askyesno(
                APP_NAME, f"Já existe um preset chamado \"{name}\". Substituir?"):
            return
        self.store.presets[name] = self.cfg.copy()
        self._save()
        messagebox.showinfo(APP_NAME, f"Preset \"{name}\" salvo em Minhas miras.")

    def delete_preset(self, name: str) -> None:
        if messagebox.askyesno(APP_NAME, f"Excluir o preset \"{name}\"?"):
            self.store.presets.pop(name, None)
            self._save()
            self.refresh_presets()

    def copy_code(self, cfg: Crosshair) -> None:
        self.clipboard_clear()
        self.clipboard_append(to_share_code(cfg))
        messagebox.showinfo(APP_NAME, "Código da mira copiado. Cole no Discord ou envie para um amigo.")

    def paste_code(self) -> None:
        code = ctk.CTkInputDialog(title="Colar código", text="Cole o código da mira (começa com PZ1:)").get_input()
        if not code:
            return
        try:
            cfg = from_share_code(code)
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        name = unique_name("Mira importada", set(BUILTIN_PRESETS) | set(self.store.presets))
        self.store.presets[name] = cfg
        self._save()
        self.refresh_presets()
        messagebox.showinfo(APP_NAME, f"Adicionada como \"{name}\".")

    def _ask_export_path(self, suggested: str) -> str:
        return filedialog.asksaveasfilename(title="Exportar", defaultextension=".json", initialfile=suggested,
                                            filetypes=[("Preset do Ponto Zero", "*.json")])

    def _export(self, presets: dict, suggested: str) -> None:
        path = self._ask_export_path(suggested)
        if not path:
            return
        try:
            export_presets(path, presets)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível exportar:\n{exc}")
            return
        messagebox.showinfo(APP_NAME, f"Exportado para:\n{path}")

    def export_current(self) -> None:
        self._export({"Minha mira": self.cfg}, "minha-mira.json")

    def export_one(self, name: str, cfg: Crosshair) -> None:
        safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name).strip() or "mira"
        self._export({name: cfg}, f"{safe}.json")

    def export_all(self) -> None:
        if not self.store.presets:
            messagebox.showinfo(APP_NAME, "Você ainda não salvou nenhum preset.")
            return
        self._export(dict(self.store.presets), "minhas-miras.json")

    def import_fivem(self) -> None:
        text = TextDialog(self, "Importar mira do FiveM",
                          "Cole os comandos que você usava no F8 (cl_crosshairsize, cl_crosshairgap...).\n"
                          "Pode colar tudo numa linha com ; ou um comando por linha.").get()
        if not text:
            return
        try:
            cfg, notes = fivem_to_crosshair(text, screen_size()[1])
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        name = unique_name("Mira do FiveM", set(BUILTIN_PRESETS) | set(self.store.presets))
        self.store.presets[name] = cfg
        self._save()
        self.use_preset(cfg)
        detail = "\n".join(notes)
        messagebox.showinfo(APP_NAME, f"Mira importada e salva como \"{name}\".\n\n"
                                      "A conversão segue o modelo do CS:GO, que o FiveM imita. Se ficar 1 px "
                                      "diferente da que você tinha, ajuste no editor." + (f"\n\n{detail}" if detail else ""))

    def import_file(self) -> None:
        path = filedialog.askopenfilename(title="Importar presets", filetypes=[("Preset do Ponto Zero", "*.json")])
        if not path:
            return
        try:
            imported = import_presets(path)
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        for name, cfg in imported.items():
            self.store.presets[unique_name(name, set(BUILTIN_PRESETS) | set(self.store.presets))] = cfg
        self._save()
        self.refresh_presets()
        messagebox.showinfo(APP_NAME, f"{len(imported)} preset(s) importado(s).")

    def on_close(self) -> None:
        if self._save_job:
            self.after_cancel(self._save_job)
        try:
            self.store.save()
        except OSError:
            pass
        if self.overlay:
            self.overlay.destroy()
        self.destroy()


def main() -> None:
    enable_dpi_awareness()
    if already_running("Local\\PontoZero.SingleInstance"):
        ctypes.windll.user32.MessageBoxW(None, "O Ponto Zero já está aberto.", APP_NAME, 0x40)
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PontoZero.MiraFixa")
    except (AttributeError, OSError):
        pass
    ctk.set_appearance_mode("dark")
    App().mainloop()
