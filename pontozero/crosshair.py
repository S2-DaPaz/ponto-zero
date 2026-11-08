"""Modelo da mira e renderizador.

Um único renderizador alimenta a pré-visualização e o overlay, para que o que se vê no
editor seja exatamente o que aparece no jogo.
"""
from __future__ import annotations

import base64
import json
import math
import re
from dataclasses import asdict, dataclass, fields

from PIL import Image, ImageChops, ImageDraw

STYLES = ("cross", "dot", "plus", "x", "circle", "corners")
STYLE_LABELS = {
    "cross": "Cruz",
    "dot": "Ponto",
    "plus": "Mais",
    "x": "X",
    "circle": "Círculo",
    "corners": "Cantos",
}

# Faixas aceitas para cada campo numérico: (mínimo, máximo).
LIMITS = {
    "size": (1, 60),
    "thickness": (1, 12),
    "gap": (0, 40),
    "dot_size": (1, 20),
    "opacity": (0, 100),
    "outline_thickness": (1, 4),
    "outline_opacity": (0, 100),
    "offset_x": (-500, 500),
    "offset_y": (-500, 500),
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
SHARE_PREFIX = "PZ1:"
SUPERSAMPLE = 4  # desenha em 4x e reduz com filtro BOX: antialiasing exato, bordas alinhadas ficam nítidas


@dataclass
class Crosshair:
    style: str = "dot"
    size: int = 4
    thickness: int = 2
    gap: int = 4
    center_dot: bool = False
    dot_size: int = 2
    square_dot: bool = False  # ponto quadrado, como o do CS:GO/FiveM
    t_style: bool = False  # cruz sem a linha de cima (cl_crosshair_t)
    color: str = "#FFFFFF"
    opacity: int = 100
    outline: bool = True
    outline_thickness: int = 1
    outline_color: str = "#000000"
    outline_opacity: int = 55
    offset_x: int = 0
    offset_y: int = 0

    @classmethod
    def from_dict(cls, data: object) -> "Crosshair":
        """Constrói a partir de dados não confiáveis: ignora chaves desconhecidas,
        corrige tipos e limita cada valor à sua faixa."""
        base = cls()
        if not isinstance(data, dict):
            return base
        values = {}
        for f in fields(cls):
            raw = data.get(f.name, getattr(base, f.name))
            default = getattr(base, f.name)
            if f.name == "style":
                values[f.name] = raw if raw in STYLES else default
            elif f.name in ("color", "outline_color"):
                values[f.name] = raw.upper() if isinstance(raw, str) and _HEX.match(raw) else default
            elif isinstance(default, bool):
                values[f.name] = raw if isinstance(raw, bool) else default
            else:
                try:
                    number = int(raw)
                except (TypeError, ValueError):
                    number = default
                lo, hi = LIMITS[f.name]
                values[f.name] = max(lo, min(hi, number))
        return cls(**values)

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self, **changes) -> "Crosshair":
        return Crosshair.from_dict({**self.to_dict(), **changes})


# Ponto do GTA V: pequeno, branco, com contorno escuro semitransparente.
GTA_DOT = Crosshair()

BUILTIN_PRESETS = {
    "GTA V (ponto)": GTA_DOT,
    "Cruz clássica": Crosshair(style="cross", size=6, thickness=2, gap=4, color="#3DF5A7",
                               outline=True, outline_opacity=70),
    "Mais": Crosshair(style="plus", size=7, thickness=2, color="#FFFFFF", outline_opacity=70),
    "X tático": Crosshair(style="x", size=6, thickness=2, gap=5, color="#FF4D6D", outline_opacity=70),
    "Círculo": Crosshair(style="circle", size=9, thickness=2, center_dot=True, dot_size=2,
                         color="#22D3EE", outline_opacity=60),
    "Cantos": Crosshair(style="corners", size=6, thickness=2, gap=3, center_dot=True, dot_size=2,
                        color="#FACC15", outline_opacity=60),
}


# --------------------------------------------------------------------------- geometria
# Cada forma é desenhada com "grow": 0 para o preenchimento, e a espessura do contorno
# para a máscara expandida. Contorno = expandida − preenchimento.

def _reach(c: Crosshair) -> float:
    """Distância máxima do centro até a borda do desenho, em px."""
    t = c.thickness
    reach = {
        "cross": t / 2 + c.gap + c.size,
        "plus": t / 2 + c.size,
        "x": (c.gap + c.size + t) * 1.0,
        "dot": c.size / 2,
        "circle": c.size,
        "corners": t / 2 + c.gap + c.size,
    }[c.style]
    if c.center_dot:
        reach = max(reach, c.dot_size / 2)
    return reach + (c.outline_thickness if c.outline else 0)


def canvas_size(c: Crosshair) -> int:
    # A paridade do canvas acompanha a da espessura: linha ímpar em canvas ímpar cai
    # inteira em pixels, sem borrar meio pixel de cada lado.
    size = 2 * math.ceil(_reach(c)) + 4
    main = c.size if c.style == "dot" else c.thickness  # a dimensão que precisa cair em pixel inteiro
    if size % 2 != main % 2:
        size += 1
    return size


def _rect(d: ImageDraw.ImageDraw, x0: float, y0: float, x1: float, y1: float, g: float) -> None:
    k = SUPERSAMPLE
    d.rectangle(
        [round((x0 - g) * k), round((y0 - g) * k), round((x1 + g) * k) - 1, round((y1 + g) * k) - 1],
        fill=255,
    )


def _disc(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, value: int = 255) -> None:
    k = SUPERSAMPLE
    if r <= 0:
        return
    d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k - 1, (cy + r) * k - 1], fill=value)


def _dot(d: ImageDraw.ImageDraw, c: Crosshair, cx: float, cy: float, diameter: float, g: float) -> None:
    if c.square_dot:
        _rect(d, cx - diameter / 2, cy - diameter / 2, cx + diameter / 2, cy + diameter / 2, g)
    else:
        _disc(d, cx, cy, diameter / 2 + g)


def _draw_shapes(img: Image.Image, c: Crosshair, center: float, g: float) -> None:
    d = ImageDraw.Draw(img)
    k = SUPERSAMPLE
    cx = cy = center
    t, h = c.thickness, c.thickness / 2

    if c.style == "circle":
        # Anel primeiro, porque o furo é "apagado" com 0 e não pode comer o ponto central.
        _disc(d, cx, cy, c.size + g)
        _disc(d, cx, cy, c.size - t - g, value=0)
    elif c.style == "dot":
        _dot(d, c, cx, cy, c.size, g)
    elif c.style == "plus":
        # Comprimentos contados a partir da borda do bloco central (h): com espessura ímpar o
        # centro cai no meio de um pixel, e só assim as pontas ficam em pixel inteiro.
        _rect(d, cx - h - c.size, cy - h, cx + h + c.size, cy + h, g)
        _rect(d, cx - h, cy - h - c.size, cx + h, cy + h + c.size, g)
    elif c.style == "cross":
        a = h + c.gap
        b = a + c.size
        _rect(d, cx + a, cy - h, cx + b, cy + h, g)
        _rect(d, cx - b, cy - h, cx - a, cy + h, g)
        _rect(d, cx - h, cy + a, cx + h, cy + b, g)
        if not c.t_style:
            _rect(d, cx - h, cy - b, cx + h, cy - a, g)
    elif c.style == "x":
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            ux, uy = dx / math.sqrt(2), dy / math.sqrt(2)
            nx, ny = -uy, ux
            start, end, half = c.gap - g, c.gap + c.size + g, h + g
            pts = [
                (cx + ux * start + nx * half, cy + uy * start + ny * half),
                (cx + ux * end + nx * half, cy + uy * end + ny * half),
                (cx + ux * end - nx * half, cy + uy * end - ny * half),
                (cx + ux * start - nx * half, cy + uy * start - ny * half),
            ]
            d.polygon([(x * k, y * k) for x, y in pts], fill=255)
    elif c.style == "corners":
        o = h + c.gap + c.size  # meia-aresta do quadrado; cada canto tem braços de "size"
        for sx in (-1, 1):
            for sy in (-1, 1):
                x_out, y_out = cx + sx * o, cy + sy * o
                x_in, y_in = x_out - sx * c.size, y_out - sy * c.size
                x_edge, y_edge = x_out - sx * t, y_out - sy * t
                _rect(d, min(x_out, x_in), min(y_out, y_edge), max(x_out, x_in), max(y_out, y_edge), g)
                _rect(d, min(x_out, x_edge), min(y_out, y_in), max(x_out, x_edge), max(y_out, y_in), g)

    if c.center_dot and c.style != "dot":
        _dot(d, c, cx, cy, c.dot_size, g)


def _symmetrize(mask: Image.Image, vertical: bool) -> Image.Image:
    # As miras são simétricas, mas o rasterizador de polígono/elipse do Pillow não é.
    mask = ImageChops.lighter(mask, mask.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
    if not vertical:  # estilo T não tem a linha de cima: espelhar de cima a baixo a recriaria
        return mask
    return ImageChops.lighter(mask, mask.transpose(Image.Transpose.FLIP_TOP_BOTTOM))


def _hex_rgb(value: str) -> tuple[int, int, int]:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def render(c: Crosshair) -> Image.Image:
    """Desenha a mira numa imagem RGBA quadrada, com o centro da mira no centro da imagem."""
    size = canvas_size(c)
    big = (size * SUPERSAMPLE, size * SUPERSAMPLE)
    center = size / 2

    fill = Image.new("L", big, 0)
    _draw_shapes(fill, c, center, 0)
    vertical = not (c.t_style and c.style == "cross")
    fill = _symmetrize(fill, vertical).resize((size, size), Image.BOX)
    fill_alpha = fill.point(lambda v: v * c.opacity // 100)
    fill_layer = Image.new("RGBA", (size, size), _hex_rgb(c.color) + (0,))
    fill_layer.putalpha(fill_alpha)

    if not c.outline:
        return fill_layer

    grown = Image.new("L", big, 0)
    _draw_shapes(grown, c, center, c.outline_thickness)
    grown = _symmetrize(grown, vertical).resize((size, size), Image.BOX)
    ring = ImageChops.subtract(grown, fill)
    outline_layer = Image.new("RGBA", (size, size), _hex_rgb(c.outline_color) + (0,))
    outline_layer.putalpha(ring.point(lambda v: v * c.outline_opacity // 100))
    return Image.alpha_composite(outline_layer, fill_layer)


# --------------------------------------------------------------------------- compartilhar
def to_share_code(c: Crosshair) -> str:
    raw = json.dumps(c.to_dict(), separators=(",", ":")).encode()
    return SHARE_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def from_share_code(code: str) -> Crosshair:
    """Levanta ValueError se o código não for um código de mira válido."""
    code = code.strip()
    if not code.startswith(SHARE_PREFIX):
        raise ValueError("O código precisa começar com " + SHARE_PREFIX)
    body = code[len(SHARE_PREFIX):]
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Código de mira corrompido") from exc
    if not isinstance(data, dict):
        raise ValueError("Código de mira corrompido")
    return Crosshair.from_dict(data)
