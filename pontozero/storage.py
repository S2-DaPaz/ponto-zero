"""Persistência em %APPDATA%\\PontoZero e importação/exportação de presets."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .crosshair import Crosshair

FILE_KIND = "pontozero-presets"
DEFAULT_SETTINGS = {"hotkey": "F9", "start_active": False}


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "PontoZero"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_dir() / "config.json"
        self.current = Crosshair()
        self.presets: dict[str, Crosshair] = {}
        self.settings = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Arquivo corrompido: guarda uma cópia para não perder os presets em silêncio.
            self.path.replace(self.path.with_suffix(".corrompido.json"))
            return
        if not isinstance(data, dict):
            return
        self.current = Crosshair.from_dict(data.get("current"))
        self.presets = parse_presets(data.get("presets"))
        settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        self.settings["hotkey"] = settings.get("hotkey", DEFAULT_SETTINGS["hotkey"])
        self.settings["start_active"] = settings.get("start_active") is True

    def save(self) -> None:
        data = {
            "version": 1,
            "current": self.current.to_dict(),
            "presets": {name: c.to_dict() for name, c in self.presets.items()},
            "settings": self.settings,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)  # troca atômica: queda de energia não deixa o arquivo pela metade


def parse_presets(raw: object) -> dict[str, Crosshair]:
    if not isinstance(raw, dict):
        return {}
    return {str(name)[:40]: Crosshair.from_dict(cfg) for name, cfg in raw.items() if isinstance(cfg, dict)}


def export_presets(path: str | Path, presets: dict[str, Crosshair]) -> None:
    data = {"kind": FILE_KIND, "version": 1, "presets": {n: c.to_dict() for n, c in presets.items()}}
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def import_presets(path: str | Path) -> dict[str, Crosshair]:
    """Levanta ValueError com mensagem legível se o arquivo não for de presets."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Não foi possível ler o arquivo: {exc}") from exc
    if not isinstance(data, dict) or data.get("kind") != FILE_KIND:
        raise ValueError("Este arquivo não é um preset do Ponto Zero.")
    presets = parse_presets(data.get("presets"))
    if not presets:
        raise ValueError("O arquivo não contém nenhum preset.")
    return presets


def unique_name(name: str, taken) -> str:
    name = name.strip()[:40] or "Minha mira"
    if name not in taken:
        return name
    i = 2
    while f"{name} ({i})" in taken:
        i += 1
    return f"{name} ({i})"
