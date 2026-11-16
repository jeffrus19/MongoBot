"""Herramientas MCP extra de MongoBot.

- self.quakes.recent      sismos recientes cerca de casa (USGS)
- self.home.*             domótica con Home Assistant
- self.memory.*           memoria personal
- self.calendar.agenda    agenda del calendario (iCal)
- self.spotify.control    Spotify en la compu
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType
from src.plugins import mongo_calendario, mongo_hogar, mongo_memoria, mongo_spotify, mongo_temblores

logger = get_logger()


def _json(d: Any) -> str:
    return json.dumps(d, ensure_ascii=False, default=str)


async def _seguro(fn, *a) -> str:
    try:
        return _json(await asyncio.to_thread(fn, *a))
    except mongo_hogar.SinConfigurar as e:
        return _json({"ok": False, "error": str(e)})
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[MongoExtra] {fn.__name__}: {e}")
        return _json({"ok": False, "error": str(e)})


# ---------------------------------------------------------------- temblores

async def quakes_recent(args: dict[str, Any]) -> str:
    def _f():
        dias = max(1, min(int(args.get("days", 1) or 1), 30))
        lista = mongo_temblores.recientes(dias, float(args.get("min_magnitude", 2.5) or 2.5),
                                          float(args.get("radius_km", 300) or 300))
        for s in lista:
            s.pop("epoch", None)
        return {"ok": True, "days": dias, "count": len(lista), "quakes": lista[:10],
                "note": "USGS: small local quakes may be missing (RSN/OVSICORI report them)"}
    return await _seguro(_f)


# ---------------------------------------------------------------- casa

async def home_devices(args: dict[str, Any]) -> str:
    return await _seguro(lambda: {"ok": True, "devices": mongo_hogar.aparatos(str(args.get("query", "")))[:40]})


async def home_control(args: dict[str, Any]) -> str:
    valor = args.get("value")
    valor = None if valor in (None, "", -1) else float(valor)
    return await _seguro(mongo_hogar.controlar, str(args.get("target", "")), str(args.get("action", "")), valor)


async def home_state(args: dict[str, Any]) -> str:
    def _f():
        e = mongo_hogar.buscar(str(args.get("target", "")), solo_controlables=False)
        return {"ok": bool(e), "matches": e[:10]} if e else {"ok": False, "error": "no encontré ese aparato"}
    return await _seguro(_f)


# ---------------------------------------------------------------- memoria

async def memory_remember(args: dict[str, Any]) -> str:
    texto = str(args.get("text", "")).strip()
    if not texto:
        return _json({"ok": False, "error": "text is required"})
    return await _seguro(lambda: {"ok": True, "saved": mongo_memoria.recordar(texto)})


async def memory_recall(args: dict[str, Any]) -> str:
    return await _seguro(lambda: {"ok": True, "matches": mongo_memoria.buscar(str(args.get("query", "")))})


async def memory_forget(args: dict[str, Any]) -> str:
    def _f():
        q = mongo_memoria.olvidar(str(args.get("which", "")))
        return {"ok": bool(q), "forgotten": q} if q else {"ok": False, "error": "no encontré ese recuerdo"}
    return await _seguro(_f)


# ---------------------------------------------------------------- calendario

async def calendar_agenda(args: dict[str, Any]) -> str:
    def _f():
        if not mongo_calendario.configurado():
            return {"ok": False, "error": "falta GOOGLE_CALENDAR_ICS_URL en mongobot_claves.json"}
        desde, hasta, desc = mongo_calendario.rango(str(args.get("when", "hoy")))
        ev = mongo_calendario.agenda(desde, hasta)
        return {"ok": True, "period": desc, "now": datetime.now().strftime("%A %d/%m %H:%M"),
                "events": [mongo_calendario.describir(e) for e in ev[:25]]}
    return await _seguro(_f)


# ---------------------------------------------------------------- Spotify

async def spotify_control(args: dict[str, Any]) -> str:
    return await _seguro(mongo_spotify.controlar, str(args.get("action", "")), str(args.get("query", "")))


def register_mongo_extra_tools(add_tool: Callable[[McpTool], None]) -> None:
    S, I, N = PropertyType.STRING, PropertyType.INTEGER, PropertyType.INTEGER
    add_tool(McpTool(
        "self.quakes.recent",
        "Recent earthquakes near home (Sabanilla, San José, Costa Rica), from USGS. ALWAYS use it when the "
        "user asks '¿tembló?', '¿hubo un temblor?', '¿de cuánto fue el temblor?'. Parameters: days (1-30, "
        "default 1), min_magnitude (default 2.5), radius_km (default 300). Answer in Spanish with magnitude, "
        "distance from home, place and time of the most relevant ones. MongoBot already warns by itself "
        "when a strong quake happens nearby.",
        PropertyList([Property("days", I, default_value=1, min_value=1, max_value=30),
                      Property("min_magnitude", S, default_value="2.5"),
                      Property("radius_km", I, default_value=300, min_value=10, max_value=2000)]),
        quakes_recent))
    add_tool(McpTool(
        "self.home.control",
        "Control the user's home through Home Assistant: lights, switches, plugs, fans, AC/thermostats, "
        "covers, locks, TVs and speakers, scenes and scripts. ALWAYS use it for 'encendé/apagá la luz de la "
        "sala', 'subí el aire a 23', 'activá la escena película', 'bajá las persianas'.\nParameters:\n"
        "- target: device name as the user says it ('luz de la sala', 'ventilador', 'tele') or entity_id.\n"
        "- action: turn_on, turn_off, toggle, brightness (value 0-100), temperature (value °C), "
        "volume (value 0-100), play_pause, open, close, lock, unlock.\n- value: number for brightness, "
        "temperature or volume (omit otherwise).\nIf it fails because the name is unclear, call "
        "self.home.devices to see the names. Confirm briefly in Spanish what you did.",
        PropertyList([Property("target", S), Property("action", S),
                      Property("value", N, default_value=-1, min_value=-1, max_value=1000)]),
        home_control))
    add_tool(McpTool(
        "self.home.devices",
        "List the devices in Home Assistant with their current state (on/off, temperature, brightness). "
        "Use it for '¿qué luces están encendidas?', '¿qué aparatos tengo?', or to find the exact name before "
        "self.home.control. Parameter: query (optional words to filter, e.g. 'luz', 'cuarto').",
        PropertyList([Property("query", S, default_value="")]),
        home_devices))
    add_tool(McpTool(
        "self.home.state",
        "State of one device or sensor in Home Assistant: '¿está encendida la luz del cuarto?', '¿qué "
        "temperatura hay en la sala?', '¿está cerrada la puerta?'. Parameter: target (name or entity_id).",
        PropertyList([Property("target", S)]),
        home_state))
    add_tool(McpTool(
        "self.memory.remember",
        "Save something the user wants you to remember about their life: where they left things, numbers, "
        "dates, names, preferences ('acordate que las llaves del carro están en la gaveta', 'anotá que el "
        "medidor de luz es el 12345'). Parameter: text (the fact, written clearly and complete, in Spanish, "
        "e.g. 'Las llaves del carro están en la gaveta del escritorio'). Confirm briefly.",
        PropertyList([Property("text", S)]),
        memory_remember))
    add_tool(McpTool(
        "self.memory.recall",
        "Look up what the user asked you to remember. ALWAYS call it before answering questions like "
        "'¿dónde dejé las llaves?', '¿cuál es el número del medidor?', '¿qué te dije de...?', '¿qué "
        "recordás?'. Parameter: query (key words; empty lists the latest). Answer from the matches; if "
        "there are none, say you have nothing saved about that.",
        PropertyList([Property("query", S, default_value="")]),
        memory_recall))
    add_tool(McpTool(
        "self.memory.forget",
        "Delete something saved with self.memory.remember ('olvidá lo de las llaves'). Parameter: which "
        "(id number or key words).",
        PropertyList([Property("which", S)]),
        memory_forget))
    add_tool(McpTool(
        "self.calendar.agenda",
        "The user's calendar (Google Calendar). ALWAYS use it for '¿qué tengo hoy?', '¿tengo algo mañana?', "
        "'¿cuándo es mi cita?', 'mi agenda de la semana'. Parameter: when = hoy | mañana | semana | a weekday "
        "(lunes...domingo) | YYYY-MM-DD. Answer briefly in Spanish with times and titles. MongoBot already "
        "warns 15 minutes before each event by itself.",
        PropertyList([Property("when", S, default_value="hoy")]),
        calendar_agenda))
    add_tool(McpTool(
        "self.spotify.control",
        "Control Spotify on the user's PC. Use it for 'pausá la música', 'siguiente canción', 'la anterior', "
        "'¿qué está sonando?', and 'poné algo de Metallica' / 'poné rock' (action open with a query). "
        "MongoBot loves metal: when asked for a recommendation without a specific artist, suggest metal "
        "(open a search for a metal band or playlist).\nParameters: action = play_pause | next | previous | "
        "now_playing | open; query = artist/album/song/genre for open.",
        PropertyList([Property("action", S), Property("query", S, default_value="")]),
        spotify_control))
    logger.info("Registradas las herramientas MCP extra de MongoBot")
