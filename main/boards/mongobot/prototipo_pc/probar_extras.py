"""Pruebas sin red de temblores, casa (Home Assistant), memoria, calendario, Spotify y
las órdenes nuevas de Telegram.

    python scripts/probar_extras.py
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.CRITICAL)

from src.plugins import (mongo_alarmas as al, mongo_calendario as cal, mongo_hogar as hogar,  # noqa: E402
                         mongo_memoria as mem, mongo_spotify as spot, mongo_telegram as tg, mongo_temblores as tem)
from src.plugins import mongo_caras                                                             # noqa: E402

TMP = Path(tempfile.mkdtemp())
mongo_caras.mostrar = lambda *a, **k: True
al._archivo = lambda: TMP / "alarmas.json"
al._cargado, al._items = True, []
mem._archivo = lambda: TMP / "memoria.json"
mem._items = None
bien = mal = 0


def ver(nombre, valor, esperado):
    global bien, mal
    ok = esperado(valor) if callable(esperado) else valor == esperado
    bien += ok
    mal += not ok
    print(f"{'ok   ' if ok else 'FALLA'} {nombre}: {valor!r}"[:160])


# ---------------------------------------------------------------- temblores
ahora = time.time()


def sismo(i, mag, lat, lon, hace=60):
    return {"id": i, "properties": {"mag": mag, "place": f"lugar {i}", "time": (ahora - hace) * 1000, "url": ""},
            "geometry": {"coordinates": [lon, lat, 10]}}


feed = {"features": [sismo("a", 4.6, 9.6, -84.2), sismo("b", 3.1, 9.9, -84.0), sismo("c", 5.8, 11.5, -86.5),
                     sismo("d", 5.0, 12.5, -87.5), sismo("e", 6.0, 9.9, -84.1, hace=3600)]}
nuevos = tem.revisar(feed, ahora)
ver("temblor fuerte cerca avisa", [s["id"] for s in nuevos], ["a", "c"])
ver("no repite", tem.revisar(feed, ahora), [])
ver("distancia Sabanilla-Cartago ~20 km", round(tem.distancia_km(9.864, -83.919)), lambda d: 10 <= d <= 25)
ver("texto del aviso", tem.texto_aviso(nuevos[0]), lambda t: t.startswith("¡Temblor! Magnitud 4.6"))

# ---------------------------------------------------------------- casa
estados = [
    {"entity_id": "light.sala", "state": "on", "attributes": {"friendly_name": "Luz de la Sala", "brightness": 128}},
    {"entity_id": "light.cuarto", "state": "off", "attributes": {"friendly_name": "Luz Cuarto"}},
    {"entity_id": "climate.aire", "state": "cool", "attributes": {"friendly_name": "Aire", "temperature": 24}},
    {"entity_id": "sensor.temp_sala", "state": "26.1", "attributes": {"friendly_name": "Temperatura sala",
                                                                       "unit_of_measurement": "°C"}},
    {"entity_id": "scene.pelicula", "state": "scening", "attributes": {"friendly_name": "Película"}},
]
llamadas = []


def ha_falso(metodo, ruta, cuerpo=None):
    if ruta == "/api/states":
        return estados
    if ruta.startswith("/api/states/"):
        return next(e for e in estados if e["entity_id"] == ruta.split("/")[-1])
    llamadas.append((ruta, cuerpo))
    return []


os.environ["HOME_ASSISTANT_URL"], os.environ["HOME_ASSISTANT_TOKEN"] = "", ""
ver("sin configurar", hogar.controlar("luz sala", "turn_on"), lambda r: False) if False else None
try:
    hogar.controlar("luz sala", "turn_on")
    ver("sin configurar avisa", "no avisó", "SinConfigurar")
except hogar.SinConfigurar:
    ver("sin configurar avisa", "SinConfigurar", "SinConfigurar")
hogar._ha = ha_falso
ver("apagar luz de la sala", hogar.controlar("la luz de la sala", "apagar"), lambda r: r["ok"] and r["devices"] == ["Luz de la Sala"])
ver("servicio llamado", llamadas[-1], ("/api/services/light/turn_off", {"entity_id": "light.sala"}))
hogar.controlar("luz sala", "brightness", 40)
ver("brillo 40 %", llamadas[-1], ("/api/services/light/turn_on", {"entity_id": "light.sala", "brightness_pct": 40}))
hogar.controlar("aire", "temperature", 23)
ver("aire a 23", llamadas[-1], ("/api/services/climate/set_temperature", {"entity_id": "climate.aire", "temperature": 23}))
hogar.controlar("pelicula", "turn_on")
ver("escena", llamadas[-1][0], "/api/services/scene/turn_on")
ver("por entity_id", hogar.controlar("light.cuarto", "toggle")["devices"], ["Luz Cuarto"])
ver("no existe", hogar.controlar("garaje", "turn_on"), lambda r: not r["ok"])
ver("acción que no aplica", hogar.controlar("aire", "lock"), lambda r: not r["ok"])
ver("estado de sensor", hogar.buscar("temperatura sala", solo_controlables=False)[0]["state"], "26.1")
ver("brillo en %", hogar.aparatos("sala")[0].get("brightness_pct"), 50)

# ---------------------------------------------------------------- memoria
mem.recordar("Las llaves del carro están en la gaveta del escritorio")
mem.recordar("El número del medidor de luz es 123456")
mem.recordar("La talla de zapatos de Jeff es 42")
ver("dónde dejé las llaves", mem.buscar("¿dónde dejé las llaves?")[0]["texto"], lambda t: "gaveta" in t)
ver("medidor", mem.buscar("número del medidor")[0]["texto"], lambda t: "123456" in t)
ver("nada", mem.buscar("pasaporte"), [])
ver("lista sin consulta", len(mem.buscar("")), 3)
ver("olvidar llaves", mem.olvidar("llaves")[0]["texto"], lambda t: "llaves" in t)
mem._items = None
ver("persiste en archivo", len(mem.todo()), 2)

# ---------------------------------------------------------------- calendario
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:u1
DTSTART;TZID=America/Costa_Rica:20261116T090000
DTEND;TZID=America/Costa_Rica:20261116T100000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6
EXDATE;TZID=America/Costa_Rica:20261118T090000
SUMMARY:Reunión de equipo
LOCATION:Oficina\\, piso 2
END:VEVENT
BEGIN:VEVENT
UID:u1
RECURRENCE-ID;TZID=America/Costa_Rica:20261123T090000
DTSTART;TZID=America/Costa_Rica:20261123T110000
DTEND;TZID=America/Costa_Rica:20261123T120000
SUMMARY:Reunión de equipo (movida)
END:VEVENT
BEGIN:VEVENT
UID:u2
DTSTART;VALUE=DATE:20261120
DTEND;VALUE=DATE:20261121
SUMMARY:Cumple de mamá
END:VEVENT
BEGIN:VEVENT
UID:u3
DTSTART:20261117T200000Z
DTEND:20261117T210000Z
SUMMARY:Dentista
END:VEVENT
BEGIN:VEVENT
UID:u4
DTSTART;TZID=America/Costa_Rica:20261119T150000
SUMMARY:Cancelada
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:u5
DTSTART;TZID=America/Costa_Rica:20260110T080000
DTEND;TZID=America/Costa_Rica:20260110T083000
RRULE:FREQ=MONTHLY;BYDAY=2TU
SUMMARY:Pago
END:VEVENT
END:VCALENDAR
"""
cal._eventos, cal._descargado = cal.leer_ics(ICS), time.time()
ver("eventos leídos (sin el cancelado)", len(cal._eventos), 5)
semana = cal.expandir(cal._eventos, datetime(2026, 11, 16), datetime(2026, 11, 26))
titulos = [f"{e['inicio']:%d %H:%M} {e['titulo']}" for e in semana]
ver("lunes 16 reunión", "16 09:00 Reunión de equipo" in titulos, True)
ver("miércoles 18 excluido", any(t.startswith("18 ") for t in titulos), False)
ver("lunes 23 movida a las 11", "23 11:00 Reunión de equipo (movida)" in titulos and "23 09:00 Reunión de equipo" not in titulos, True)
ver("dentista en hora local", any("Dentista" in t for t in titulos), True)
ver("todo el día", [e["todo_el_dia"] for e in semana if e["titulo"] == "Cumple de mamá"], [True])
ver("lugar con coma", next(e["lugar"] for e in semana if e["lugar"]), "Oficina, piso 2")
dic = cal.expandir(cal._eventos, datetime(2026, 12, 1), datetime(2026, 12, 31))
ver("segundo martes de diciembre", [f"{e['inicio']:%d}" for e in dic if e["titulo"] == "Pago"], ["08"])
ver("COUNT=6 se respeta", len([e for e in cal.expandir(cal._eventos, datetime(2026, 11, 1), datetime(2027, 2, 1))
                               if e["titulo"].startswith("Reunión")]), 5)
d, h, desc = cal.rango("viernes", date(2026, 11, 16))
ver("rango viernes", (d.day, h.day), (20, 21))
cal._avisados.clear()
ver("aviso 15 min antes", [e["titulo"] for e in cal.por_avisar(datetime(2026, 11, 16, 8, 46))], ["Reunión de equipo"])
ver("no repite el aviso", cal.por_avisar(datetime(2026, 11, 16, 8, 50)), [])
ver("todo el día no avisa", cal.por_avisar(datetime(2026, 11, 19, 23, 50)), [])

# ---------------------------------------------------------------- Spotify (fuera de Windows)
if sys.platform != "win32":
    ver("Spotify fuera de Windows", spot.controlar("next"), lambda r: not r["ok"])

# ---------------------------------------------------------------- Telegram
ver("/anotar", tg.responder("/anotar el wifi de invitados es casa2026"), lambda r: r.startswith("Guardado"))
ver("/buscar", tg.responder("/buscar wifi invitados"), lambda r: "casa2026" in r)
ver("/encender sin HA", tg.responder("/encender luz sala"), lambda r: r.startswith("Listo"))
ver("texto suelto no para nada", tg.responder("ya voy llegando"), "Listo, lo puse en la pantalla.")
al._sonando = {"item": {"tipo": "alarma", "texto": ""}, "veces": 1, "ultimo": time.time()}
ver("'pará' con la alarma sonando", tg.responder("pará"), "Listo, la callé.")
al._sonando = None
ver("'detené la alarma'", tg.responder("detené la alarma"), "No estaba sonando nada.")
os.environ["GOOGLE_CALENDAR_ICS_URL"] = ""
ver("/agenda sin URL", tg.responder("/agenda"), lambda r: "GOOGLE_CALENDAR_ICS_URL" in r)

# ---------------------------------------------------------------- herramientas registradas
from src.mcp.tools.mongo_extra import register_mongo_extra_tools   # noqa: E402
herr = []
register_mongo_extra_tools(herr.append)
ver("herramientas", sorted(t.name for t in herr), lambda n: len(n) == 9 and len(set(n)) == 9)
r = json.loads(asyncio.run(next(t for t in herr if t.name == "self.memory.recall").callback({"query": "medidor"})))
ver("self.memory.recall", r["matches"][0]["texto"], lambda t: "123456" in t)

print(f"\n{bien} bien, {mal} fallas")
sys.exit(1 if mal else 0)
