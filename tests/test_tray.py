import uuid

import pystray
from PIL import Image

from pontozero.overlay import ShowSignal, signal_show
from pontozero.tray import Tray


def test_show_signal_reaches_the_running_instance_once():
    name = f"Local\\PontoZeroTeste.{uuid.uuid4().hex}"
    running = ShowSignal(name)
    assert running.poll() is False
    assert signal_show(name) is True  # segunda execução do exe
    assert running.poll() is True
    assert running.poll() is False  # consumido: não reabre a janela em loop


def test_signal_show_without_running_instance_returns_false():
    assert signal_show(f"Local\\PontoZeroTeste.{uuid.uuid4().hex}") is False


def test_tray_menu_turns_clicks_into_commands():
    tray = Tray(Image.new("RGBA", (16, 16)), "Ponto Zero", start=False)
    items = [item for item in tray.icon.menu.items if item is not pystray.Menu.SEPARATOR]
    assert [item.text for item in items] == ["Abrir Ponto Zero", "Ligar/desligar mira", "Sair"]
    for item in items:
        item(tray.icon)
    assert [tray.commands.get_nowait() for _ in items] == ["show", "toggle", "quit"]
    assert tray.commands.empty()


def test_left_click_opens_the_window():
    tray = Tray(Image.new("RGBA", (16, 16)), "Ponto Zero", start=False)
    tray.icon.menu(tray.icon)  # o que o clique esquerdo faz (Icon.__call__): executa o item padrão
    assert tray.commands.get_nowait() == "show"


def test_tray_not_started_is_not_ready():
    tray = Tray(Image.new("RGBA", (16, 16)), "Ponto Zero", start=False)
    assert tray.ready() is False
