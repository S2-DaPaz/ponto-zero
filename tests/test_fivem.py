import pytest

from pontozero.crosshair import Crosshair, render
from pontozero.fivem import to_crosshair

# Colado exatamente como um usuário mandou, inclusive as aspas por fora.
USER_DOT = ('"cl_crosshairalpha "255";cl_crosshaircolor "5";cl_crosshaircolor_b "255";cl_crosshaircolor_r "255";'
            'cl_crosshaircolor_g "255";cl_crosshairdot "1";cl_crosshairgap "-4";cl_crosshairsize "0";'
            'cl_crosshairstyle "4";cl_crosshairusealpha "1";cl_crosshairthickness "1.6";cl_fixedcrosshairgap "-3";'
            'cl_crosshair_outlinethickness "1";cl_crosshair_drawoutline "1""')

# Exemplo do manual oficial da Cfx.
CFX_MANUAL = ("cl_customcrosshair 1;cl_crosshairstyle 5;cl_crosshairsize 3.5;cl_crosshair_drawoutline 1;"
              "cl_crosshairthickness 1;cl_crosshair_outlinethickness 0.4;cl_crosshairdot 0;cl_crosshairgap -1")


def test_user_dot_becomes_white_square_dot_with_outline():
    cfg, notes = to_crosshair(USER_DOT, 1080)
    assert notes == []
    assert cfg.style == "dot"
    assert cfg.size == 4  # 1.6 * 1080/480 = 3.6 -> 4 px
    assert cfg.square_dot is True
    assert cfg.color == "#FFFFFF"
    assert cfg.opacity == 100
    assert cfg.outline is True and cfg.outline_thickness == 1
    alpha = render(cfg).getchannel("A")
    box = alpha.getbbox()
    assert box[2] - box[0] == 6  # 4 px de ponto + 1 px de contorno de cada lado
    assert set(alpha.tobytes()) <= {0, 255}  # quadrado alinhado: nada borrado


def test_cfx_manual_example_is_cross_with_gap():
    cfg, _ = to_crosshair(CFX_MANUAL, 1080)
    assert cfg.style == "cross"
    assert cfg.thickness == 2  # 1 * 2.25
    assert cfg.size == 8  # 3.5 * 2.25 = 7.875
    assert cfg.gap == 2  # início da linha a 4 + (-1) = 3 px do centro, menos meia espessura
    assert cfg.color == "#32FA32"  # sem cl_crosshaircolor: verde padrão do CS:GO
    assert cfg.opacity == 78  # alpha 200


def test_one_command_per_line_and_preset_color():
    cfg, _ = to_crosshair("cl_crosshairsize 2\ncl_crosshairgap 0\ncl_crosshaircolor 4\ncl_crosshair_t 1", 1080)
    assert cfg.color == "#32FAFA"
    assert cfg.t_style is True
    img = render(cfg).getchannel("A")
    mid = img.size[0] // 2
    column = [img.getpixel((mid, y)) for y in range(img.size[1])]
    assert not any(column[:mid - 3]), "estilo T não pode ter a linha de cima"
    assert any(column[mid + 3:])


def test_negative_gap_turns_into_plus():
    cfg, _ = to_crosshair("cl_crosshairsize 3;cl_crosshairgap -5;cl_crosshairthickness 1", 1080)
    assert cfg.style == "plus"


def test_errors_and_unknown_commands():
    with pytest.raises(ValueError):
        to_crosshair("bind f4 something", 1080)
    with pytest.raises(ValueError):
        to_crosshair("cl_crosshairsize 0;cl_crosshairdot 0", 1080)
    _, notes = to_crosshair("cl_crosshairsize 3;cl_crosshairfoo 2;cl_crosshair_dynamic_splitdist 7", 1080)
    assert notes == ["Comando ignorado: cl_crosshairfoo"]


def test_scales_with_screen_height():
    small, _ = to_crosshair(CFX_MANUAL, 720)
    big, _ = to_crosshair(CFX_MANUAL, 1440)
    assert small.size < big.size


def test_old_presets_without_new_fields_still_load():
    old = Crosshair().to_dict()
    old.pop("square_dot")
    old.pop("t_style")
    assert Crosshair.from_dict(old) == Crosshair()
