"""Puente entre la herramienta MCP de caras y la pantalla de MongoBot.

La herramienta ``self.screen.show_face`` (src/mcp/tools/cara) llama a ``mostrar``.
La pantalla (UiPresenter) se conecta con ``conectar``. Mientras una cara pedida
está activa, la pantalla no deja que otra cosa la tape (por ejemplo, el cambio a
"hablando" que pone la cara neutral); al terminar el tiempo vuelve a la última
cara que se quiso mostrar.

Si la cara es la guitarra o el videojuego, en Windows también suena su loop mientras dure.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from pathlib import Path

from src.logging import get_logger

logger = get_logger()

_mostrar_en_pantalla: Callable[[str], None] | None = None
_bloqueada_hasta = 0.0
_pendiente: str | None = None
_temporizador: asyncio.TimerHandle | None = None
_sonando = False
_hasta_respuesta = False      # la cara se suelta cuando MongoBot termina de contestar
CON_SONIDO = ("guitarra", "videojuego")     # caras que llevan un loop de audio
GOLPES = {"llamando": True, "saludo": False}  # MongoBot toca la pantalla: nombre -> se repite


def conectar(fn: Callable[[str], None] | None) -> None:
    """La pantalla registra cómo poner una cara (o None al cerrarse)."""
    global _mostrar_en_pantalla
    _mostrar_en_pantalla = fn


def dura_hasta_respuesta() -> bool:
    return bloqueada() and _hasta_respuesta


def bloqueada() -> bool:
    return time.monotonic() < _bloqueada_hasta


def guardar_pendiente(nombre: str) -> None:
    """Lo que alguien quiso mostrar mientras había una cara pedida."""
    global _pendiente
    _pendiente = nombre


def carpeta_caras() -> Path:
    from src.utils.resource_finder import get_assets_dir

    return get_assets_dir() / "emojis"


def caras_disponibles() -> list[str]:
    carpeta = carpeta_caras()
    if not carpeta.is_dir():
        return []
    return sorted(p.stem for p in carpeta.glob("*.gif"))


def _sonido(nombre: str, encender: bool, suave: bool = False) -> None:
    """Sonido de la cara mientras dure (solo Windows, con winsound): loop de la guitarra
    o del videojuego (8 bits), o los golpes en el vidrio de llamando y saludo.
    ``suave``: la versión a volumen moderado (la de inactividad)."""
    global _sonando
    if sys.platform != "win32":
        return
    try:
        import winsound

        if encender and (nombre in CON_SONIDO or nombre in GOLPES):
            from src.utils.resource_finder import get_assets_dir

            carpeta = get_assets_dir() / "inactividad"
            wav = carpeta / (f"{nombre}_suave.wav" if suave else f"{nombre}.wav")
            if not wav.exists():
                wav = carpeta / f"{nombre}.wav"
            if wav.exists():
                repite = winsound.SND_LOOP if GOLPES.get(nombre, True) else 0
                winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC | repite)
                _sonando = True
        elif _sonando:
            winsound.PlaySound(None, 0)
            _sonando = False
    except Exception as e:                                   # noqa: BLE001
        logger.debug(f"[MongoCaras] sin sonido: {e}")


def _liberar() -> None:
    global _bloqueada_hasta, _temporizador, _pendiente, _hasta_respuesta
    _bloqueada_hasta = 0.0
    _hasta_respuesta = False
    _temporizador = None
    _sonido("", False)
    siguiente = _pendiente
    if siguiente is None:
        try:
            from src.plugins import mongo_comportamiento

            c = mongo_comportamiento.actual()
            siguiente = c.cara if c and c.cara else None
        except Exception:                                    # noqa: BLE001
            siguiente = None
    siguiente = siguiente or "neutral"
    _pendiente = None
    if _mostrar_en_pantalla:
        _mostrar_en_pantalla(siguiente)
    logger.info(f"[MongoCaras] fin de la cara pedida, vuelve a {siguiente}")


def soltar() -> None:
    """Termina ya la cara pedida y vuelve a la que toca."""
    global _temporizador
    if _temporizador is not None:
        _temporizador.cancel()
        _temporizador = None
    if bloqueada():
        _liberar()


def mostrar(nombre: str, segundos: float, hasta_respuesta: bool = False) -> bool:
    """Pone la cara ``nombre`` durante ``segundos``. Devuelve False si no hay pantalla.
    ``hasta_respuesta``: además se suelta en cuanto MongoBot termina de contestar
    (p. ej. el clima: la cara acompaña la respuesta, ni más ni menos)."""
    global _bloqueada_hasta, _temporizador, _hasta_respuesta
    if _mostrar_en_pantalla is None:
        return False
    _sonido("", False)
    _mostrar_en_pantalla(nombre)
    _bloqueada_hasta = time.monotonic() + segundos
    _hasta_respuesta = hasta_respuesta
    _sonido(nombre, True)
    try:
        loop = asyncio.get_running_loop()
        if _temporizador is not None:
            _temporizador.cancel()
        _temporizador = loop.call_later(segundos, _liberar)
    except RuntimeError:
        _temporizador = None
    logger.info(f"[MongoCaras] mostrando {nombre} por {segundos:.0f} s")
    return True
