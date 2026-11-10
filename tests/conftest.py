import os

# Backend falso do pystray nos testes: o win32 registra uma classe de janela por ícone com id()
# no nome e nunca a remove; com o endereço reaproveitado pelo GC, o RegisterClassEx falha (1410).
os.environ.setdefault("PYSTRAY_BACKEND", "dummy")
