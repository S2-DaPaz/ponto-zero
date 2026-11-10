"""Decisões da janela com a bandeja: X, comandos do ícone e o laço de 40 ms."""
import queue
import time
import uuid

import pytest
from PIL import Image

from pontozero import app as A
from pontozero.overlay import ShowSignal, signal_show
from pontozero.tray import Tray


class FakeOverlay:
    def __init__(self):
        self.visible = False
        self.destroyed = False

    def draw(self, img, offset_x=0, offset_y=0):
        pass

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def raise_to_top(self):
        pass

    def destroy(self):
        self.destroyed = True


class FakeTray:
    def __init__(self, ready):
        self.commands = queue.Queue()
        self._is_ready = ready
        self.stopped = False

    def ready(self, timeout=0):
        return self._is_ready

    def set_title(self, title):
        pass

    def stop(self):
        self.stopped = True


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(A, "Overlay", FakeOverlay)
    apps = []

    def build(tray_ready=True, show_signal=None):
        tray = FakeTray(tray_ready)
        monkeypatch.setattr(A, "Tray", lambda image, title: tray)
        app = A.App(show_signal=show_signal)
        apps.append(app)
        return app, tray

    yield build
    for app in apps:
        if not app._quitting:
            app.destroy()


def pump(app, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def test_x_hides_to_tray_and_keeps_the_crosshair(make_app):
    app, tray = make_app(tray_ready=True)
    app.set_active(True)
    app.hide_to_tray()
    assert app.state() == "withdrawn"
    assert app._quitting is False
    assert app.overlay.visible and not app.overlay.destroyed and not tray.stopped


def test_x_closes_for_real_when_tray_is_not_ready(make_app):
    app, tray = make_app(tray_ready=False)
    overlay = app.overlay
    app.hide_to_tray()
    assert app._quitting is True
    assert overlay.destroyed and tray.stopped


def test_show_and_toggle_commands_run_on_the_tk_thread(make_app):
    app, tray = make_app()
    app.withdraw()
    tray.commands.put("show")
    tray.commands.put("toggle")
    app._poll()
    assert app.state() == "normal"
    assert app.active is True and app.overlay.visible


def test_quit_command_ends_the_app(make_app):
    app, tray = make_app()
    overlay = app.overlay
    tray.commands.put("quit")
    app._poll()
    assert app._quitting is True
    assert overlay.destroyed and tray.stopped


def test_poll_keeps_running_after_an_error(make_app, monkeypatch):
    # Com a janela escondida, o laço é o único caminho de volta: um erro não pode pará-lo.
    app, tray = make_app()
    app.after_cancel(app._poll_job)
    app.withdraw()

    def broken(active):
        raise RuntimeError("falha qualquer")

    monkeypatch.setattr(app, "set_active", broken)
    tray.commands.put("toggle")
    with pytest.raises(RuntimeError):
        app._poll()
    tray.commands.put("show")
    pump(app)
    assert app.state() == "normal"
    assert tray.commands.empty()


def test_second_launch_signal_shows_the_hidden_window(make_app):
    name = f"Local\\PontoZeroTeste.{uuid.uuid4().hex}"
    app, _ = make_app(show_signal=ShowSignal(name))
    app.withdraw()
    assert signal_show(name)
    app._poll()
    assert app.state() == "normal"


class FakeIcon:
    def __init__(self, accept=True):
        self.calls = []
        self._visible = False
        self.accept = accept

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self.calls.append(f"visible={value}")
        self._visible = value and self.accept

    def stop(self):
        self.calls.append("stop")


def make_tray(icon):
    tray = Tray(Image.new("RGBA", (16, 16)), "Ponto Zero", start=False)
    tray.icon = icon
    return tray


def test_ready_only_after_setup_shows_the_icon():
    tray = make_tray(FakeIcon())
    assert tray.ready() is False
    tray._setup(tray.icon)
    assert tray.ready() is True


def test_not_ready_when_icon_refused_to_show():
    tray = make_tray(FakeIcon(accept=False))
    tray._setup(tray.icon)
    assert tray.ready() is False


def test_stop_removes_icon_before_ending_its_thread():
    # Tirar o ícone na thread do Tk, antes de parar o laço: senão quem remove é a thread
    # daemon, correndo contra o fim do processo (ícone fantasma).
    icon = FakeIcon()
    tray = make_tray(icon)
    tray._setup(icon)
    tray.stop()
    assert icon.calls == ["visible=True", "visible=False", "stop"]
