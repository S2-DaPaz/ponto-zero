"""Ícone na área de notificação do Windows.

O pystray roda o próprio laço de mensagens numa thread separada. Os cliques nunca tocam a
interface diretamente (Tk não é thread-safe): viram comandos numa fila que a thread do Tk lê.
"""
from __future__ import annotations

import queue
import threading

import pystray
from PIL import Image


class Tray:
    """Ícone com menu Abrir · Ligar/desligar mira · Sair; o clique esquerdo abre a janela."""

    def __init__(self, image: Image.Image, title: str, start: bool = True) -> None:
        """Monta o ícone e, com `start`, o mostra numa thread própria."""
        self.commands: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()
        menu = pystray.Menu(
            pystray.MenuItem("Abrir Ponto Zero", lambda: self.commands.put("show"), default=True),
            pystray.MenuItem("Ligar/desligar mira", lambda: self.commands.put("toggle")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda: self.commands.put("quit")),
        )
        self.icon = pystray.Icon("PontoZero", image, title, menu)
        if start:
            threading.Thread(target=self.icon.run, args=(self._setup,), daemon=True).start()

    def _setup(self, icon: pystray.Icon) -> None:
        """Roda quando o laço do ícone está pronto: torna o ícone visível e libera ready()."""
        try:
            icon.visible = True
        finally:
            self._ready.set()

    def ready(self, timeout: float = 0) -> bool:
        """True se o ícone está de fato na bandeja; espera até `timeout` segundos."""
        # ponytail: o pystray marca visible sem conferir o retorno do Shell_NotifyIcon, então um
        # Explorer que recuse o ícone passa por pronto. Há volta (reabrir o exe mostra a janela);
        # conferir de verdade exigiria API privada do pystray.
        return self._ready.wait(timeout) and self.icon.visible

    def set_title(self, title: str) -> None:
        """Troca o texto que aparece ao passar o mouse no ícone."""
        self.icon.title = title

    def stop(self) -> None:
        """Remove o ícone e encerra a thread dele."""
        if self.ready():
            # Remove aqui, de forma síncrona: deixado para a thread daemon, o NIM_DELETE corre
            # contra o fim do processo e pode sobrar um ícone fantasma.
            self.icon.visible = False
            self.icon.stop()
