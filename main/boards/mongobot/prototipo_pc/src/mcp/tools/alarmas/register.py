"""Herramientas MCP de alarmas, temporizadores y recordatorios de MongoBot.

Cuando llega la hora, MongoBot grita "¡RING RING RING!" con su voz (ver
src/plugins/mongo_alarmas.py).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()


def _ok(**datos) -> str:
    datos.setdefault("now", datetime.now().strftime("%A %d/%m/%Y %H:%M"))
    return json.dumps({"ok": True, **datos}, ensure_ascii=False)


def _error(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg, "now": datetime.now().strftime("%A %d/%m/%Y %H:%M")},
                      ensure_ascii=False)


def register_alarma_tools(add_tool: Callable[[McpTool], None]) -> None:
    from src.plugins import mongo_alarmas as al
    from src.plugins import mongo_caras

    async def set_alarm(args: dict[str, Any]) -> str:
        try:
            h, m = al.leer_hora(args["time"])
        except Exception:
            return _error("time must look like '06:30' or '18:05'")
        dias = al.leer_dias(args.get("days", ""))
        cuando = al.proxima(h, m, dias)
        it = al.programar("alarma", cuando, args.get("label", ""), dias, (h, m))
        mongo_caras.mostrar("alarma", 3)
        return _ok(scheduled=al.describir(it), id=it["id"])

    async def set_timer(args: dict[str, Any]) -> str:
        total = int(args.get("minutes", 0)) * 60 + int(args.get("seconds", 0))
        if total <= 0:
            return _error("give minutes and/or seconds greater than 0")
        it = al.programar("temporizador", datetime.now() + timedelta(seconds=total), args.get("label", ""))
        mongo_caras.mostrar("temporizador", 4)
        return _ok(scheduled=al.describir(it), id=it["id"], seconds=total)

    async def set_reminder(args: dict[str, Any]) -> str:
        texto = str(args.get("text", "")).strip()
        if not texto:
            return _error("text is required: what to remind")
        hora = str(args.get("time", "")).strip()
        en_min = int(args.get("in_minutes", 0))
        dias = al.leer_dias(args.get("days", ""))
        if hora:
            try:
                h, m = al.leer_hora(hora)
            except Exception:
                return _error("time must look like '15:00'")
            it = al.programar("recordatorio", al.proxima(h, m, dias), texto, dias, (h, m))
        elif en_min > 0:
            it = al.programar("recordatorio", datetime.now() + timedelta(minutes=en_min), texto)
        else:
            return _error("give time ('15:00') or in_minutes (> 0)")
        mongo_caras.mostrar("recordatorio", 3)
        return _ok(scheduled=al.describir(it), id=it["id"])

    async def list_alarms(args: dict[str, Any]) -> str:
        items = al.listar()
        return _ok(count=len(items), items=[al.describir(it) for it in items])

    async def cancel_alarm(args: dict[str, Any]) -> str:
        quitadas = al.cancelar(str(args.get("id", "")))
        if not quitadas:
            return _error("there is no alarm to cancel with that id/time")
        return _ok(cancelled=[al.describir(it) for it in quitadas])

    async def stop_ringing(args: dict[str, Any]) -> str:
        return _ok(stopped=al.detener())

    al_sonar = ("IMPORTANT: when a message arrives that starts with 'RING RING RIIIIING', it is NOT the user "
                "talking: it is one of these alarms going off. Then just shout that exact message, word by word "
                "(e.g. 'RING RING RIIIIING ¡ALARMA!'), and nothing else: do not ask anything, do not offer to set "
                "another alarm, do not comment. "
                "The alarm keeps ringing every 30 seconds until the user explicitly tells you to stop it; "
                "if they talk about something else, answer but do NOT stop it.\n")
    dias_ayuda = ("days: optional repeat. '' = only once, 'diario' = every day, 'lun-vie' = weekdays, "
                  "'fin de semana', or a list like 'lun,mie,vie'.")
    tools = [
        McpTool(
            "self.alarm.set_alarm",
            ("Set an alarm at a clock time (local time). When it rings, MongoBot shouts 'RING RING RING'.\n"
             + al_sonar +
             "Use for: 'pon una alarma a las 6:30', 'coloca una alarma a las 7 pm', 'poneme una alarma a las 6:30', "
             "'programá una alarma para las 5', 'despertame a las 7', 'alarma de lunes a viernes a las 6'. "
             "When the user asks for an alarm and says a time, ALWAYS call this tool right away (never just say "
             "it is set). NEVER ask what the alarm is for, its name, which alarm or any other detail: label is "
             "optional, leave it empty if not said. Only if no time was said at all, ask just the time.\n"
             "Parameters:\n- time: 'HH:MM' 24h, or '6:30 am' / '7 pm'.\n- " + dias_ayuda + "\n"
             "- label: optional short note (e.g. 'gimnasio')."),
            PropertyList([Property("time", PropertyType.STRING),
                          Property("days", PropertyType.STRING, default_value=""),
                          Property("label", PropertyType.STRING, default_value="")]),
            set_alarm,
        ),
        McpTool(
            "self.alarm.set_timer",
            ("Start a countdown timer. When it ends, MongoBot shouts 'RING RING RING'.\n"
             + al_sonar +
             "Use for: 'temporizador de 10 minutos', 'avisame en 30 segundos', 'cuenta 5 minutos'.\n"
             "Parameters: minutes, seconds (at least one > 0), label (optional, e.g. 'arroz')."),
            PropertyList([Property("minutes", PropertyType.INTEGER, default_value=0, min_value=0, max_value=1440),
                          Property("seconds", PropertyType.INTEGER, default_value=0, min_value=0, max_value=3600),
                          Property("label", PropertyType.STRING, default_value="")]),
            set_timer,
        ),
        McpTool(
            "self.alarm.set_reminder",
            ("Set a reminder. At that moment MongoBot shouts 'RING RING RING' and says what to do.\n"
             + al_sonar +
             "Use for: 'recordame a las 3 llamar al banco', 'en 20 minutos recordame sacar la ropa'.\n"
             "Parameters:\n- text: what to remind (required).\n- time: 'HH:MM' (use this OR in_minutes).\n"
             "- in_minutes: minutes from now.\n- " + dias_ayuda),
            PropertyList([Property("text", PropertyType.STRING),
                          Property("time", PropertyType.STRING, default_value=""),
                          Property("in_minutes", PropertyType.INTEGER, default_value=0, min_value=0, max_value=10080),
                          Property("days", PropertyType.STRING, default_value="")]),
            set_reminder,
        ),
        McpTool(
            "self.alarm.list_alarms",
            "List all scheduled alarms, timers and reminders with their ids. Use for '¿qué alarmas tengo?'.",
            PropertyList(),
            list_alarms,
        ),
        McpTool(
            "self.alarm.cancel_alarm",
            ("Cancel a scheduled alarm, timer or reminder. id can be: a time ('6:30', '7 pm') to cancel the ones "
             "at that time, a number id, 'all' to cancel everything, or empty to cancel the next one. "
             "NEVER ask which alarm: if the user does not say, leave id empty.\n"
             "Use for: 'quitá la alarma de las 6:30', 'cancelá la alarma', 'borrá todas las alarmas'."),
            PropertyList([Property("id", PropertyType.STRING, default_value="")]),
            cancel_alarm,
        ),
        McpTool(
            "self.alarm.stop_ringing",
            ("Stop the alarm that is ringing right now. Use ONLY when the user explicitly asks to stop it: "
             "'para', 'detené la alarma', 'apagá la alarma', 'ya', 'basta', 'callate', 'ya me levanté'. "
             "Talking about something else does not stop it."),
            PropertyList(),
            stop_ringing,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("Registradas %d herramientas MCP de alarmas", len(tools))
