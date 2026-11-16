"""Calendario: MongoBot lee tu Google Calendar y te avisa de las citas.

Usa la "dirección secreta en formato iCal" del calendario (solo lectura, sin cuentas
ni permisos): Google Calendar en la compu > Configuración > tu calendario >
Integrar el calendario > Dirección secreta en formato iCal. Esa URL va en
mongobot_claves.json como GOOGLE_CALENDAR_ICS_URL (se pueden poner varias separadas
por espacios). Funciona igual con Outlook o iCloud si dan una URL .ics.

- Herramienta self.calendar.agenda: "¿qué tengo hoy?", "¿qué tengo el viernes?".
- AVISO_MIN minutos antes de cada cita con hora: cara de recordatorio, texto en
  pantalla, Telegram y "¡CITA EN 15 MINUTOS!".

Costa Rica no tiene horario de verano (UTC-6 todo el año): las horas con zona
America/Costa_Rica o sin zona se toman como hora local.
"""

from __future__ import annotations

import asyncio
import calendar as _cal
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

from src.logging import get_logger
from src.plugins import mongo_avisos, mongo_claves

logger = get_logger()

AVISO_MIN = 15
REVISAR_CADA = 60               # segundos entre revisiones de avisos
DESCARGAR_CADA = 10 * 60        # segundos entre descargas del .ics
DIAS_ADELANTE = 60
_DIAS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_eventos: list[dict] = []
_descargado = 0.0
_avisados: set[str] = set()


# ---------------------------------------------------------------- lectura del .ics

def _lineas(texto: str) -> list[str]:
    salida: list[str] = []
    for linea in texto.replace("\r\n", "\n").split("\n"):
        if linea[:1] in (" ", "\t") and salida:
            salida[-1] += linea[1:]
        elif linea:
            salida.append(linea)
    return salida


def _valor(texto: str) -> str:
    return (texto.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"))


def _fecha(params: dict, valor: str) -> tuple[datetime, bool]:
    """-> (datetime local sin zona, es_de_todo_el_dia)."""
    valor = valor.strip()
    if params.get("VALUE") == "DATE" or (len(valor) == 8 and valor.isdigit()):
        return datetime.strptime(valor[:8], "%Y%m%d"), True
    if valor.endswith("Z"):
        utc = datetime.strptime(valor[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        return utc.astimezone().replace(tzinfo=None), False
    local = datetime.strptime(valor[:15], "%Y%m%dT%H%M%S")
    zona = params.get("TZID", "")
    if zona and zona not in ("America/Costa_Rica", "Central America Standard Time"):
        try:
            from zoneinfo import ZoneInfo

            return local.replace(tzinfo=ZoneInfo(zona)).astimezone().replace(tzinfo=None), False
        except Exception:                                        # noqa: BLE001
            pass
    return local, False


def _propiedad(linea: str) -> tuple[str, dict, str]:
    cabeza, _, valor = linea.partition(":")
    partes = cabeza.split(";")
    params = {}
    for p in partes[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v.strip('"')
    return partes[0].upper(), params, valor


def leer_ics(texto: str) -> list[dict]:
    eventos, actual = [], None
    for linea in _lineas(texto):
        if linea == "BEGIN:VEVENT":
            actual = {"exdate": []}
        elif linea == "END:VEVENT" and actual is not None:
            if "inicio" in actual and actual.get("estado") != "CANCELLED":
                eventos.append(actual)
            actual = None
        elif actual is not None:
            nombre, params, valor = _propiedad(linea)
            if nombre == "SUMMARY":
                actual["titulo"] = _valor(valor)
            elif nombre == "LOCATION":
                actual["lugar"] = _valor(valor)
            elif nombre == "UID":
                actual["uid"] = valor
            elif nombre == "STATUS":
                actual["estado"] = valor.upper()
            elif nombre == "DTSTART":
                actual["inicio"], actual["todo_el_dia"] = _fecha(params, valor)
            elif nombre == "DTEND":
                actual["fin"], _ = _fecha(params, valor)
            elif nombre == "RRULE":
                actual["rrule"] = dict(p.split("=", 1) for p in valor.split(";") if "=" in p)
            elif nombre == "EXDATE":
                for v in valor.split(","):
                    actual["exdate"].append(_fecha(params, v)[0])
            elif nombre == "RECURRENCE-ID":
                actual["reemplaza"] = _fecha(params, valor)[0]
    return eventos


# ---------------------------------------------------------------- repeticiones

def _sumar_meses(d: datetime, n: int) -> datetime | None:
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    if d.day > _cal.monthrange(a, m)[1]:
        return None
    return d.replace(year=a, month=m)


def _repeticiones(ev: dict, desde: datetime, hasta: datetime) -> list[datetime]:
    inicio, r = ev["inicio"], ev.get("rrule")
    if not r:
        return [inicio]
    freq, intervalo = r.get("FREQ", ""), int(r.get("INTERVAL", "1") or 1)
    cuenta = int(r["COUNT"]) if "COUNT" in r else None
    limite = hasta
    if "UNTIL" in r:
        limite = min(limite, _fecha({}, r["UNTIL"])[0] + timedelta(days=1 if len(r["UNTIL"]) == 8 else 0))
    dias = [_DIAS[d[-2:]] for d in r.get("BYDAY", "").split(",") if d[-2:] in _DIAS]
    salida, n, paso = [], 0, 0
    while paso < 5000:
        if freq == "DAILY":
            candidatos = [inicio + timedelta(days=paso * intervalo)]
        elif freq == "WEEKLY":
            base = inicio + timedelta(weeks=paso * intervalo)
            lunes = base - timedelta(days=base.weekday())
            candidatos = sorted(lunes + timedelta(days=d) for d in (dias or [inicio.weekday()]))
            candidatos = [c for c in candidatos if c >= inicio]
        elif freq == "MONTHLY":
            c = _sumar_meses(inicio, paso * intervalo)
            candidatos = [c] if c else []
            byday = r.get("BYDAY", "")
            m = re.fullmatch(r"(-?\d)([A-Z]{2})", byday)
            if m:                                        # p. ej. 2TU: segundo martes del mes
                mes = _sumar_meses(inicio.replace(day=1), paso * intervalo)
                semana, dia = int(m.group(1)), _DIAS[m.group(2)]
                fechas = [mes.replace(day=k) for k in range(1, _cal.monthrange(mes.year, mes.month)[1] + 1)
                          if mes.replace(day=k).weekday() == dia]
                try:
                    candidatos = [fechas[semana - 1 if semana > 0 else semana]]
                except IndexError:
                    candidatos = []
        elif freq == "YEARLY":
            c = _sumar_meses(inicio, 12 * paso * intervalo)
            candidatos = [c] if c else []
        else:
            return [inicio]
        if candidatos and candidatos[0] > limite:
            break
        for c in candidatos:
            if c > limite or (cuenta is not None and n >= cuenta):
                return salida
            n += 1
            if c >= desde - timedelta(days=1) and c not in ev["exdate"]:
                salida.append(c)
        if cuenta is not None and n >= cuenta:
            break
        paso += 1
    return salida


def expandir(eventos: list[dict], desde: datetime, hasta: datetime) -> list[dict]:
    reemplazos = {(e.get("uid"), e["reemplaza"]) for e in eventos if "reemplaza" in e}
    salida = []
    for ev in eventos:
        dur = (ev.get("fin") or ev["inicio"] + timedelta(hours=1)) - ev["inicio"]
        for c in _repeticiones(ev, desde, hasta):
            if "reemplaza" not in ev and (ev.get("uid"), c) in reemplazos:
                continue
            fin = c + dur
            if fin > desde and c < hasta:
                salida.append({"titulo": ev.get("titulo", "(sin título)"), "inicio": c, "fin": fin,
                               "todo_el_dia": ev["todo_el_dia"], "lugar": ev.get("lugar", ""),
                               "clave": f"{ev.get('uid', ev.get('titulo'))}@{c:%Y%m%d%H%M}"})
    return sorted(salida, key=lambda e: e["inicio"])


# ---------------------------------------------------------------- descarga y consultas

def _urls() -> list[str]:
    return [u for u in mongo_claves.clave("GOOGLE_CALENDAR_ICS_URL").split() if u.startswith("http")]


def descargar() -> list[dict]:
    global _eventos, _descargado
    todos = []
    for url in _urls():
        req = urllib.request.Request(url, headers={"User-Agent": mongo_avisos.UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            todos += leer_ics(r.read().decode("utf-8", "replace"))
    _eventos, _descargado = todos, time.time()
    return todos


def configurado() -> bool:
    return bool(_urls())


def agenda(desde: datetime, hasta: datetime) -> list[dict]:
    if time.time() - _descargado > DESCARGAR_CADA or not _eventos:
        descargar()
    return expandir(_eventos, desde, hasta)


def rango(cuando: str, hoy: date | None = None) -> tuple[datetime, datetime, str]:
    """'hoy', 'mañana', 'semana', 'viernes', '2026-11-20' -> (desde, hasta, descripción)."""
    hoy = hoy or date.today()
    c = mongo_avisos.normalizar(cuando or "hoy").strip()
    inicio = datetime.combine(hoy, datetime.min.time())
    if c in ("", "hoy", "today"):
        return datetime.now(), inicio + timedelta(days=1), "hoy"
    if c in ("manana", "tomorrow"):
        return inicio + timedelta(days=1), inicio + timedelta(days=2), "mañana"
    if c in ("semana", "week", "esta semana", "proximos dias"):
        return datetime.now(), inicio + timedelta(days=7), "los próximos 7 días"
    nombres = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
    if c in nombres:
        d = (nombres[c] - hoy.weekday()) % 7 or 7
        dia = inicio + timedelta(days=d)
        return dia, dia + timedelta(days=1), cuando
    dia = datetime.strptime(c[:10], "%Y-%m-%d")
    return dia, dia + timedelta(days=1), dia.strftime("%d/%m")


def describir(e: dict) -> str:
    hora = "todo el día" if e["todo_el_dia"] else f"{e['inicio']:%H:%M}–{e['fin']:%H:%M}"
    lugar = f" ({e['lugar']})" if e.get("lugar") else ""
    return f"{e['inicio']:%a %d/%m} {hora}: {e['titulo']}{lugar}"


def por_avisar(ahora: datetime) -> list[dict]:
    salida = []
    for e in expandir(_eventos, ahora - timedelta(minutes=1), ahora + timedelta(minutes=AVISO_MIN + 1)):
        falta = (e["inicio"] - ahora).total_seconds() / 60
        if not e["todo_el_dia"] and 0 <= falta <= AVISO_MIN and e["clave"] not in _avisados:
            _avisados.add(e["clave"])
            salida.append(e)
    return salida


async def correr() -> None:
    logger.info(f"[MongoCalendario] listo (avisa {AVISO_MIN} min antes de cada cita)")
    while True:
        try:
            if configurado():
                if time.time() - _descargado > DESCARGAR_CADA:
                    await asyncio.to_thread(descargar)
                for e in por_avisar(datetime.now()):
                    mins = max(1, round((e["inicio"] - datetime.now()).total_seconds() / 60))
                    mongo_avisos.avisar(f"En {mins} min: {e['titulo']} ({e['inicio']:%H:%M})"
                                        + (f" en {e['lugar']}" if e.get("lugar") else ""),
                                        cara="recordatorio", segundos=20,
                                        voz=f"¡CITA EN {mins} MINUTOS!")
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.warning(f"[MongoCalendario] {e}")
        await asyncio.sleep(REVISAR_CADA)
