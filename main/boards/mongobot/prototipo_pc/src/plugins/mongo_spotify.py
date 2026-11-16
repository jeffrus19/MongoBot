"""Música en serio: MongoBot maneja Spotify en la compu (Windows).

Sin cuentas ni claves: usa las teclas multimedia de Windows (las mismas del teclado)
y lee el título de la ventana de Spotify, que muestra "Artista - Canción" mientras
suena. Funciona con la app de escritorio de Spotify abierta (gratis o Premium).

- self.spotify.control: play/pausa, siguiente, anterior, qué está sonando, y abrir
  Spotify buscando un artista, disco o canción ("poné algo de Metallica").
- Mientras suena Spotify, MongoBot pone la cara de música, como con su reproductor.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import urllib.parse

from src.logging import get_logger

logger = get_logger()

REVISAR_CADA = 4
TECLAS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}
_SIN_CANCION = ("spotify", "spotify premium", "spotify free", "")
_ultimo_estado: str | None = None


def disponible() -> bool:
    return sys.platform == "win32"


def _tecla(vk: int) -> None:
    import ctypes

    u = ctypes.windll.user32
    u.keybd_event(vk, 0, 1, 0)          # KEYEVENTF_EXTENDEDKEY
    u.keybd_event(vk, 0, 3, 0)          # + KEYEVENTF_KEYUP


def _titulos_spotify() -> list[str]:
    """Títulos de las ventanas visibles del proceso Spotify.exe."""
    import ctypes
    from ctypes import wintypes

    import psutil

    pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "spotify.exe"}
    if not pids:
        return []
    u = ctypes.windll.user32
    titulos: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cada(hwnd, _):
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(hwnd):
            n = u.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, buf, n + 1)
                titulos.append(buf.value)
        return True

    u.EnumWindows(_cada, 0)
    return titulos


def sonando() -> dict:
    """{'abierto': bool, 'sonando': bool, 'artista': str, 'cancion': str}."""
    if not disponible():
        return {"abierto": False, "sonando": False, "artista": "", "cancion": ""}
    titulos = _titulos_spotify()
    for t in titulos:
        if t.strip().lower() not in _SIN_CANCION and " - " in t:
            artista, _, cancion = t.partition(" - ")
            return {"abierto": True, "sonando": True, "artista": artista.strip(), "cancion": cancion.strip()}
    return {"abierto": bool(titulos), "sonando": False, "artista": "", "cancion": ""}


def controlar(accion: str, consulta: str = "") -> dict:
    if not disponible():
        return {"ok": False, "error": "el control de Spotify solo funciona en Windows"}
    a = accion.lower()
    if a in ("now_playing", "que_suena", "status"):
        return {"ok": True, **sonando()}
    if a in ("open", "search", "buscar", "play_search"):
        if not consulta.strip():
            return {"ok": False, "error": "query is required to open a search"}
        os.startfile("spotify:search:" + urllib.parse.quote(consulta.strip()))   # type: ignore[attr-defined]
        return {"ok": True, "opened": consulta, "note": "Spotify quedó abierto con la búsqueda; el usuario "
                "elige qué reproducir (o usa play_pause si ya había algo en cola)"}
    if a in TECLAS:
        if a == "play_pause" and not sonando()["abierto"]:
            os.startfile("spotify:")                                             # type: ignore[attr-defined]
            time.sleep(3)
        _tecla(TECLAS[a])
        time.sleep(1.2)
        return {"ok": True, "action": a, **sonando()}
    return {"ok": False, "error": f"acción desconocida: {accion}"}


async def correr() -> None:
    """Mientras suena Spotify, MongoBot pone la cara de música."""
    global _ultimo_estado
    if not disponible():
        return
    from src.plugins import mongo_comportamiento

    while True:
        try:
            estado = "playing" if (await asyncio.to_thread(sonando))["sonando"] else "paused"
            if estado != _ultimo_estado:
                if _ultimo_estado is not None or estado == "playing":
                    c = mongo_comportamiento.actual()
                    if c is not None:
                        c.al_musica(estado)
                _ultimo_estado = estado
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.debug(f"[MongoSpotify] {e}")
        await asyncio.sleep(REVISAR_CADA)
