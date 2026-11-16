"""Bot de Telegram de MongoBot.

Desde el celular le podés escribir al bot para:

    /estado                  si está conectado, qué cara tiene y la próxima alarma
    /alarma 6:30 [nota]      programa una alarma
    /recordar 18:00 texto    recordatorio a una hora (o "/recordar 20m texto", "2h")
    /temporizador 10m [nota] temporizador
    /lista                   alarmas, temporizadores y recordatorios programados
    /cancelar [id|hora|todas] borra (sin nada: la próxima)
    /parar                   calla la alarma que esté sonando
    /mensaje texto           lo muestra en la pantalla (cualquier texto suelto, también)
    /ayuda

Y MongoBot te avisa por Telegram cuando suena una alarma, un temporizador o un
recordatorio (los pomodoros no avisan).

Solo obedece al chat de TELEGRAM_CHAT_ID. Si todavía no está puesto, al primer mensaje
contesta con el número de tu chat para que lo copies a mongobot_claves.json. El token
(TELEGRAM_BOT_TOKEN) lo da @BotFather. Usa la API de Bot de Telegram con long polling:
no hace falta abrir puertos.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from src.logging import get_logger
from src.plugins import mongo_claves

logger = get_logger()

_API = "https://api.telegram.org/bot{token}/{metodo}"
ESPERA = 30                 # segundos de long polling
SIN_TOKEN_REVISAR = 60      # sin token: cada cuánto vuelve a mirar el archivo de claves
MENSAJE_EN_PANTALLA = 12    # segundos que se ve la cara "mensaje"
RELATIVO = re.compile(r"^(\d+)\s*(s|seg|m|min|h|hr|hora|horas)$", re.IGNORECASE)

AYUDA = (
    "Soy MongoBot. Esto es lo que entiendo:\n"
    "/estado – cómo estoy y la próxima alarma\n"
    "/alarma 6:30 [nota]\n"
    "/recordar 18:00 sacar la basura (o /recordar 20m ...)\n"
    "/temporizador 10m [nota]\n"
    "/lista – lo programado\n"
    "/cancelar [id | hora | todas] – sin nada borra la próxima\n"
    "/parar – callo la alarma que esté sonando\n"
    "/mensaje texto – lo pongo en mi pantalla (o escribime cualquier cosa)"
)

_loop: asyncio.AbstractEventLoop | None = None


# ---------------------------------------------------------------- API de Telegram

def _llamar(token: str, metodo: str, params: dict[str, Any], timeout: float) -> Any:
    url = _API.format(token=token, metodo=metodo)
    datos = urllib.parse.urlencode(params).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=datos), timeout=timeout) as r:
        respuesta = json.loads(r.read().decode("utf-8"))
    if not respuesta.get("ok"):
        raise RuntimeError(respuesta.get("description", "respuesta no ok"))
    return respuesta.get("result")


def _enviar(token: str, chat_id: str, texto: str) -> None:
    try:
        _llamar(token, "sendMessage", {"chat_id": chat_id, "text": texto[:4000]}, 15)
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[MongoTelegram] no pude mandar el mensaje: {e}")


def avisar(texto: str) -> None:
    """Manda un aviso a tu chat, sin bloquear. No hace nada si falta el token o el chat."""
    token = mongo_claves.clave("TELEGRAM_BOT_TOKEN")
    chat = mongo_claves.clave("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = _loop
    if loop is None:
        return
    loop.call_soon_threadsafe(lambda: loop.create_task(asyncio.to_thread(_enviar, token, chat, texto)))


# ---------------------------------------------------------------- órdenes

def _cuando(texto: str) -> tuple[datetime, tuple[int, int] | None]:
    """'6:30', '7 pm', '20m', '2h', '45s' -> (cuándo, (h, m) si fue una hora fija)."""
    from src.plugins import mongo_alarmas as al

    t = texto.strip().lower()
    m = RELATIVO.match(t)
    if m:
        n, u = int(m.group(1)), m.group(2)
        seg = n * (3600 if u.startswith("h") else 60 if u.startswith("m") else 1)
        return datetime.now() + timedelta(seconds=seg), None
    h, mi = al.leer_hora(t)
    return al.proxima(h, mi, []), (h, mi)


def _partir_hora(resto: str) -> tuple[str, str]:
    """'7 pm sacar la basura' -> ('7 pm', 'sacar la basura'); '6:30 nota' -> ('6:30', 'nota')."""
    partes = resto.split()
    if len(partes) >= 2 and partes[1].lower().strip(".") in ("am", "pm", "a.m", "p.m"):
        return " ".join(partes[:2]), " ".join(partes[2:])
    return (partes[0] if partes else ""), " ".join(partes[1:])


def _estado() -> str:
    from src.plugins import mongo_alarmas as al
    from src.plugins import mongo_comportamiento

    lineas = [f"Estoy encendido. Son las {datetime.now():%H:%M}."]
    c = mongo_comportamiento.actual()
    if c is not None:
        lineas.append(f"Cara: {c.cara or 'neutral'}" + (" (durmiendo)" if getattr(c, "_dormido", False) else ""))
    proximas = al.listar()
    lineas.append(f"Próxima: {al.describir(proximas[0])}" if proximas else "No hay nada programado.")
    return "\n".join(lineas)


def _mostrar_mensaje(texto: str) -> str:
    from src.plugins import mongo_caras, mongo_comportamiento

    mongo_caras.mostrar("mensaje", MENSAJE_EN_PANTALLA)
    c = mongo_comportamiento.actual()
    if c is not None:
        c._texto(f"Mensaje: {texto}")
    logger.info(f"[MongoTelegram] mensaje en pantalla: {texto}")
    return "Listo, lo puse en la pantalla."


def responder(texto: str) -> str:
    """Atiende un mensaje de tu chat y devuelve la respuesta. Sin red: se puede probar."""
    from src.plugins import mongo_alarmas as al

    texto = (texto or "").strip()
    if not texto:
        return AYUDA
    if not texto.startswith("/"):
        return _mostrar_mensaje(texto)
    orden, _, resto = texto.partition(" ")
    orden = orden[1:].split("@")[0].lower()
    resto = resto.strip()
    try:
        if orden in ("start", "ayuda", "help"):
            return AYUDA
        if orden == "estado":
            return _estado()
        if orden in ("alarma", "recordar", "recordatorio", "temporizador", "timer"):
            tipo = {"recordar": "recordatorio", "timer": "temporizador"}.get(orden, orden)
            cuando_txt, nota = _partir_hora(resto)
            if not cuando_txt:
                return f"Decime cuándo. Ej.: /{orden} " + ("10m arroz" if tipo == "temporizador" else "6:30")
            if tipo == "recordatorio" and not nota:
                return "Decime qué te recuerdo. Ej.: /recordar 18:00 sacar la basura"
            cuando, hora = _cuando(cuando_txt)
            if tipo == "temporizador" and hora is not None:
                return "Para el temporizador decime cuánto tiempo. Ej.: /temporizador 10m arroz"
            it = al.programar(tipo, cuando, nota, [], hora)
            return f"Listo: {al.describir(it)}"
        if orden == "lista":
            items = al.listar()
            return "\n".join(al.describir(it) for it in items) if items else "No hay nada programado."
        if orden == "cancelar":
            quitadas = al.cancelar(resto)
            return ("Borré: " + "; ".join(al.describir(it) for it in quitadas)) if quitadas \
                else "No encontré nada para cancelar."
        if orden in ("parar", "detener", "callate"):
            return "Listo, la callé." if al.detener() else "No estaba sonando nada."
        if orden == "mensaje":
            return _mostrar_mensaje(resto) if resto else "Escribí el mensaje después de /mensaje."
    except ValueError:
        return "No entendí la hora. Probá con 6:30, 7 pm, 20m o 2h."
    return "No conozco esa orden.\n\n" + AYUDA


# ---------------------------------------------------------------- bucle

async def correr() -> None:
    """Escucha los mensajes del bot. Lo arranca el plugin de UI."""
    global _loop
    _loop = asyncio.get_running_loop()
    mongo_claves.asegurar_campos(["TAVILY_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    offset: int | None = None
    avisado_sin_token = False
    while True:
        token = mongo_claves.clave("TELEGRAM_BOT_TOKEN")
        if not token:
            if not avisado_sin_token:
                logger.info("[MongoTelegram] sin TELEGRAM_BOT_TOKEN en mongobot_claves.json: bot apagado")
                avisado_sin_token = True
            await asyncio.sleep(SIN_TOKEN_REVISAR)
            continue
        avisado_sin_token = False
        try:
            if offset is None:
                # al arrancar se saltan los mensajes viejos que quedaron pendientes
                viejos = await asyncio.to_thread(_llamar, token, "getUpdates", {"offset": -1, "timeout": 0}, 15)
                offset = (viejos[-1]["update_id"] + 1) if viejos else 0
                logger.info("[MongoTelegram] bot escuchando")
            updates = await asyncio.to_thread(
                _llamar, token, "getUpdates",
                {"offset": offset, "timeout": ESPERA, "allowed_updates": '["message"]'}, ESPERA + 10)
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.warning(f"[MongoTelegram] {e}; reintento en 15 s")
            await asyncio.sleep(15)
            continue
        for u in updates or []:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            texto = msg.get("text") or ""
            if not chat:
                continue
            permitido = mongo_claves.clave("TELEGRAM_CHAT_ID")
            if not permitido:
                logger.info(f"[MongoTelegram] mensaje de un chat sin autorizar todavía: {chat}")
                await asyncio.to_thread(_enviar, token, chat,
                                        f"Tu chat_id es {chat}. Ponelo en mongobot_claves.json como "
                                        "TELEGRAM_CHAT_ID y desde ahí te hago caso.")
                continue
            if chat != permitido:
                logger.warning(f"[MongoTelegram] ignoro un mensaje de otro chat ({chat})")
                continue
            respuesta = responder(texto)
            await asyncio.to_thread(_enviar, token, chat, respuesta)
