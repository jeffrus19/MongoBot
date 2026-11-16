"""Avisos que MongoBot da por su cuenta (temblores, citas del calendario...).

Un aviso pone una cara, escribe el texto en pantalla, manda un Telegram y, si se pide,
dice una frase corta en voz alta (el servidor rechaza los textos largos, así que la
frase va de pocas palabras y el detalle queda en pantalla y en Telegram).
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import json
from typing import Any

from src.logging import get_logger

logger = get_logger()

VOZ_MAX = 27                 # "RING RING RIIIIING ¡ALARMA!" pasa; textos más largos los rechaza
UA = "MongoBot/1.0 (asistente de voz personal; py-xiaozhi)"


def avisar(texto: str, cara: str = "", segundos: float = 15, voz: str = "", telegram: bool = True) -> None:
    try:
        from src.plugins import mongo_caras, mongo_comportamiento

        if cara:
            mongo_caras.mostrar(cara, segundos)
        c = mongo_comportamiento.actual()
        if c is not None:
            c._texto(texto)
    except Exception as e:                                       # noqa: BLE001
        logger.debug(f"[MongoAvisos] sin pantalla: {e}")
    if telegram:
        try:
            from src.plugins import mongo_telegram

            mongo_telegram.avisar(texto)
        except Exception as e:                                   # noqa: BLE001
            logger.debug(f"[MongoAvisos] sin Telegram: {e}")
    if voz:
        _decir(voz[:VOZ_MAX])
    logger.info(f"[MongoAvisos] {texto}")


def _decir(frase: str) -> None:
    import asyncio

    from src.plugins import mongo_alarmas

    if mongo_alarmas._enviar is None:
        return
    try:
        asyncio.get_running_loop().create_task(mongo_alarmas._enviar(frase))
    except RuntimeError:
        pass


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
             timeout: float = 15, data: Any = None, method: str | None = None) -> Any:
    """GET/POST con urllib que devuelve el JSON."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = {"User-Agent": UA, **(headers or {})}
    cuerpo = None
    if data is not None:
        cuerpo = json.dumps(data).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=cuerpo, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        texto = r.read().decode("utf-8", "replace")
    return json.loads(texto) if texto.strip() else None


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres ("Luz de la Sala" ~ "luz sala")."""
    import unicodedata

    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
