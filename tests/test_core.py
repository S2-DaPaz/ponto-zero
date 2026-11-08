import json

import pytest

from pontozero.crosshair import (BUILTIN_PRESETS, STYLES, Crosshair, canvas_size, from_share_code, render,
                                 to_share_code)
from pontozero.storage import Store, export_presets, import_presets, unique_name


def test_from_dict_clamps_and_rejects_garbage():
    c = Crosshair.from_dict({"style": "nuke", "size": 9999, "gap": -5, "color": "red",
                             "outline": "yes", "opacity": "50", "extra": 1})
    assert c.style == "dot"
    assert c.size == 60
    assert c.gap == 0
    assert c.color == "#FFFFFF"
    assert c.outline is True  # string não vira bool: fica o padrão
    assert c.opacity == 50


def test_from_dict_non_dict_returns_default():
    assert Crosshair.from_dict(None) == Crosshair()
    assert Crosshair.from_dict([1, 2]) == Crosshair()


@pytest.mark.parametrize("style", STYLES)
def test_every_style_renders_centered_and_symmetric(style):
    c = Crosshair(style=style, size=8, thickness=2, gap=3, center_dot=True)
    img = render(c)
    assert img.size == (canvas_size(c),) * 2
    alpha = img.getchannel("A")
    assert alpha.getbbox() is not None, "mira desenhada vazia"
    # Todas as miras são simétricas: espelhar não pode mudar a imagem.
    assert alpha.tobytes() == alpha.transpose(0).tobytes()
    assert alpha.tobytes() == alpha.transpose(1).tobytes()


@pytest.mark.parametrize("thickness", [1, 2, 3])
def test_straight_lines_are_crisp(thickness):
    # Linha alinhada em pixel inteiro não pode ter borda semitransparente.
    c = Crosshair(style="plus", size=6, thickness=thickness, outline=False)
    alpha = render(c).getchannel("A")
    assert set(alpha.tobytes()) <= {0, 255}


def test_gta_dot_is_white_with_dark_soft_outline():
    gta = BUILTIN_PRESETS["GTA V (ponto)"]
    img = render(gta)
    mid = img.size[0] // 2
    r, g, b, a = img.getpixel((mid, mid))
    assert (r, g, b, a) == (255, 255, 255, 255)
    alphas = [img.getpixel((x, mid))[3] for x in range(img.size[0])]
    edge = next(x for x, value in enumerate(alphas) if value)
    assert img.getpixel((edge, mid))[:3] == (0, 0, 0)
    assert 0 < img.getpixel((edge, mid))[3] < 255


def test_opacity_scales_alpha():
    c = Crosshair(style="plus", size=5, thickness=2, outline=False, opacity=50)
    assert max(render(c).getchannel("A").tobytes()) == 127


def test_share_code_round_trip_and_errors():
    c = Crosshair(style="x", size=12, color="#FF00AA", offset_x=-3)
    assert from_share_code(to_share_code(c)) == c
    with pytest.raises(ValueError):
        from_share_code("abc")
    with pytest.raises(ValueError):
        from_share_code("PZ1:%%%")


def test_store_round_trip(tmp_path):
    path = tmp_path / "config.json"
    store = Store(path)
    store.current = Crosshair(style="circle", size=10)
    store.presets["Teste"] = Crosshair(style="corners")
    store.settings["hotkey"] = "F10"
    store.save()
    again = Store(path)
    assert again.current == store.current
    assert again.presets == store.presets
    assert again.settings["hotkey"] == "F10"


def test_store_survives_corrupt_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    store = Store(path)
    assert store.current == Crosshair()
    assert (tmp_path / "config.corrompido.json").exists()


def test_import_export(tmp_path):
    path = tmp_path / "miras.json"
    export_presets(path, {"A": Crosshair(style="plus")})
    assert import_presets(path) == {"A": Crosshair(style="plus")}
    other = tmp_path / "outro.json"
    other.write_text(json.dumps({"foo": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        import_presets(other)


def test_unique_name():
    assert unique_name("Mira", {"Mira", "Mira (2)"}) == "Mira (3)"
    assert unique_name("  ", set()) == "Minha mira"
