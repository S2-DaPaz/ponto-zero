"""Importa a mira dos comandos de F8 do FiveM (cl_crosshair*).

O manual da Cfx diz que o crosshair do FiveM imita o do CS:GO e aceita as configs dele.
O código de desenho do FiveM não é aberto, então a conversão segue o modelo do CS:GO:
comprimento e espessura em 1/480 da altura da tela, espaço = 4 + cl_crosshairgap em pixels.
ponytail: aproximação documentada, não medição; se divergir no jogo, corrigir aqui as fórmulas.
"""
from __future__ import annotations

import re

from .crosshair import Crosshair

_COMMAND = re.compile(r'\b(cl_[a-z_]+)\s+"?(-?[\w.]+)"?', re.IGNORECASE)

# Cores pré-definidas de cl_crosshaircolor 0-4 (5 = RGB próprio), valores do CS:GO.
PRESET_COLORS = {0: (250, 50, 50), 1: (50, 250, 50), 2: (250, 250, 50), 3: (50, 50, 250), 4: (50, 250, 250)}

# Valores padrão do CS:GO para o que o usuário não informar.
DEFAULTS = {
    "cl_crosshairsize": 5.0, "cl_crosshairthickness": 0.5, "cl_crosshairgap": 1.0,
    "cl_fixedcrosshairgap": 3.0, "cl_crosshairdot": False, "cl_crosshairstyle": 4,
    "cl_crosshaircolor": 1, "cl_crosshaircolor_r": 50, "cl_crosshaircolor_g": 250, "cl_crosshaircolor_b": 50,
    "cl_crosshairusealpha": True, "cl_crosshairalpha": 200, "cl_crosshair_drawoutline": False,
    "cl_crosshair_outlinethickness": 1.0, "cl_crosshair_t": False, "cl_customcrosshair": True,
}
_IGNORED_PREFIX = "cl_crosshair_dynamic_"  # sem efeito no FiveM, segundo o manual


def _bool(value: str) -> bool:
    """Lê booleano no formato do console: 1/true/yes/on."""
    return value.strip().lower() in ("1", "true", "yes", "on")


def parse(text: str) -> tuple[dict, list[str]]:
    """Lê os comandos em qualquer formato (com ou sem aspas, separados por ; ou por linha)."""
    values, unknown = {}, []
    for name, raw in _COMMAND.findall(text):
        key = name.lower()
        if key.startswith(_IGNORED_PREFIX):
            continue
        if key not in DEFAULTS:
            unknown.append(name)
            continue
        default = DEFAULTS[key]
        try:
            if isinstance(default, bool):
                values[key] = _bool(raw)
            elif isinstance(default, int):
                values[key] = int(float(raw))
            else:
                values[key] = float(raw)
        except ValueError:
            unknown.append(f"{name} {raw}")
    if not values:
        raise ValueError("Nenhum comando de mira do FiveM encontrado. Cole os comandos cl_crosshair....")
    return values, unknown


def to_crosshair(text: str, screen_height: int) -> tuple[Crosshair, list[str]]:
    """Converte para uma mira do Ponto Zero. Devolve também avisos para mostrar ao usuário."""
    given, unknown = parse(text)
    v = {**DEFAULTS, **given}
    notes = [f"Comando ignorado: {name}" for name in unknown]
    unit = screen_height / 480

    thickness = max(1, round(v["cl_crosshairthickness"] * unit))
    length = max(0, round(v["cl_crosshairsize"] * unit))
    gap_cmd = v["cl_fixedcrosshairgap"] if v["cl_crosshairstyle"] in (0, 1) else v["cl_crosshairgap"]
    inner = round(4 + gap_cmd)  # distância do centro até o início de cada linha

    if v["cl_crosshaircolor"] in PRESET_COLORS:
        rgb = PRESET_COLORS[v["cl_crosshaircolor"]]
    else:
        rgb = tuple(max(0, min(255, int(v[f"cl_crosshaircolor_{ch}"]))) for ch in "rgb")
    alpha = v["cl_crosshairalpha"] if v["cl_crosshairusealpha"] else 200
    opacity = round(max(0, min(255, alpha)) / 255 * 100)

    common = dict(
        thickness=thickness,
        color="#{:02X}{:02X}{:02X}".format(*rgb),
        opacity=opacity,
        outline=v["cl_crosshair_drawoutline"],
        outline_thickness=max(1, round(v["cl_crosshair_outlinethickness"])),
        outline_color="#000000",
        outline_opacity=opacity,  # no CS:GO o contorno usa a mesma transparência da mira
        square_dot=True,
        dot_size=thickness,  # no CS:GO o ponto é um quadrado com lado igual à espessura
    )
    half = thickness / 2

    if length == 0:
        if not v["cl_crosshairdot"]:
            raise ValueError("Esses comandos não desenham nada: sem linhas (cl_crosshairsize 0) e sem ponto.")
        cfg = Crosshair(style="dot", size=thickness, **common)
    elif inner <= half:
        # Espaço negativo: as linhas encostam ou cruzam o centro, o que vira um "+".
        cfg = Crosshair(style="plus", size=max(1, round(inner + length - half)),
                        center_dot=v["cl_crosshairdot"], **common)
    else:
        cfg = Crosshair(style="cross", size=length, gap=round(inner - half), center_dot=v["cl_crosshairdot"],
                        t_style=v["cl_crosshair_t"], **common)
        if v["cl_crosshair_t"]:
            notes.append("Estilo T aplicado (sem a linha de cima).")

    if given.get("cl_customcrosshair") is False:
        notes.append("Os comandos tinham cl_customCrosshair false; a mira foi importada mesmo assim.")
    if v["cl_crosshairstyle"] in (0, 1):
        notes.append("Estilo 0/1 do CS:GO (dinâmico padrão) convertido como mira fixa.")
    return Crosshair.from_dict(cfg.to_dict()), notes
