"""Overlay da mira: janela Win32 com transparência por pixel, clicável através e sempre no topo.

Não lê nem escreve memória do jogo — só desenha um bitmap no centro da tela.
A janela é da classe de sistema "Static" e vive na thread do Tk, cujo laço de eventos
já despacha as mensagens de todas as janelas da thread.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020  # cliques atravessam a janela
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080  # fora do Alt+Tab e da barra de tarefas
WS_EX_NOACTIVATE = 0x08000000  # nunca rouba o foco do jogo
ULW_ALPHA = 0x2
AC_SRC_ALPHA = 0x1
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = w.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
SM_CXSCREEN, SM_CYSCREEN = 0, 1
ERROR_ALREADY_EXISTS = 183


class BLENDFUNCTION(ctypes.Structure):
    """Estrutura BLENDFUNCTION do Win32 para UpdateLayeredWindow."""
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    """Cabeçalho de bitmap DIB do Win32."""
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
                ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG),
                ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD)]


class BITMAPINFO(ctypes.Structure):
    """BITMAPINFO do Win32 (cabeçalho mais a tabela de cores, não usada em 32 bits)."""
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


# Sem restype explícito o ctypes trunca handles em int de 32 bits no Python 64 bits.
user32.CreateWindowExW.restype = w.HWND
user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
user32.GetDC.restype = w.HDC
user32.GetDC.argtypes = [w.HWND]
user32.ReleaseDC.argtypes = [w.HWND, w.HDC]
user32.UpdateLayeredWindow.argtypes = [w.HWND, w.HDC, ctypes.POINTER(w.POINT), ctypes.POINTER(w.SIZE),
                                       w.HDC, ctypes.POINTER(w.POINT), w.COLORREF,
                                       ctypes.POINTER(BLENDFUNCTION), w.DWORD]
user32.UpdateLayeredWindow.restype = w.BOOL
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
user32.DestroyWindow.argtypes = [w.HWND]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
gdi32.CreateCompatibleDC.restype = w.HDC
gdi32.CreateCompatibleDC.argtypes = [w.HDC]
gdi32.CreateDIBSection.restype = w.HBITMAP
gdi32.CreateDIBSection.argtypes = [w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD]
gdi32.SelectObject.restype = w.HGDIOBJ
gdi32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
gdi32.DeleteObject.argtypes = [w.HGDIOBJ]
gdi32.DeleteDC.argtypes = [w.HDC]
kernel32.CreateMutexW.restype = w.HANDLE
kernel32.CreateMutexW.argtypes = [w.LPVOID, w.BOOL, w.LPCWSTR]

# Teclas de atalho aceitas: nome exibido -> virtual-key code.
HOTKEYS = {f"F{i}": 0x6F + i for i in range(1, 13)}
HOTKEYS.update({"Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x23,
                "Page Up": 0x21, "Page Down": 0x22, "Pause": 0x13, "Scroll Lock": 0x91})
HOTKEYS.update({f"Num {i}": 0x60 + i for i in range(10)})


def enable_dpi_awareness() -> None:
    """Sem isto, com escala de 125%/150% o Windows mente o tamanho da tela e a mira sai do centro."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def already_running(name: str) -> bool:
    """Mutex nomeado: duas instâncias desenhariam duas miras."""
    handle = kernel32.CreateMutexW(None, False, name)
    already_running.handle = handle  # mantém o handle vivo enquanto o processo existir
    return ctypes.get_last_error() == ERROR_ALREADY_EXISTS


def screen_size() -> tuple[int, int]:
    """Resolução da tela principal em pixels físicos."""
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)


def key_down(vk: int) -> bool:
    """Se a tecla está pressionada agora, mesmo com outro programa em foco."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _to_premultiplied_bgra(img: Image.Image) -> bytes:
    """Converte RGBA do Pillow para BGRA pré-multiplicado, o formato do UpdateLayeredWindow."""
    r, g, b, a = img.convert("RGBa").split()  # "RGBa" = RGB pré-multiplicado pelo alfa
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


class Overlay:
    """Janela da mira sobre o jogo."""
    def __init__(self) -> None:
        """Cria a janela escondida; levanta OSError se o Windows recusar."""
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "Static", "Ponto Zero Overlay", WS_POPUP, 0, 0, 1, 1, None, None, None, None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.visible = False

    def draw(self, img: Image.Image, offset_x: int = 0, offset_y: int = 0) -> None:
        """Posiciona a imagem com o centro dela no centro da tela (mais o deslocamento)."""
        width, height = img.size
        sw, sh = screen_size()
        dst = w.POINT(sw // 2 - width // 2 + offset_x, sh // 2 - height // 2 + offset_y)
        data = _to_premultiplied_bgra(img)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # negativo = linhas de cima para baixo, como o Pillow
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32

        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(mem_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(mem_dc, bitmap)
            blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self.hwnd, screen_dc, ctypes.byref(dst), ctypes.byref(w.SIZE(width, height)),
                                       mem_dc, ctypes.byref(w.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
            gdi32.SelectObject(mem_dc, old)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(None, screen_dc)

    def show(self) -> None:
        """Mostra a janela sem tirar o foco do jogo."""
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        self.visible = True
        self.raise_to_top()

    def hide(self) -> None:
        """Esconde a janela."""
        user32.ShowWindow(self.hwnd, SW_HIDE)
        self.visible = False

    def raise_to_top(self) -> None:
        """Jogos em janela sem bordas às vezes sobem na ordem Z; chamado periodicamente."""
        if self.visible:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def destroy(self) -> None:
        """Destrói a janela do Windows."""
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
