"""Pruebas sin red del bot de Telegram y de la búsqueda web de MongoBot.

    python scripts/probar_telegram_busqueda.py
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.CRITICAL)

from src.plugins import mongo_alarmas as al          # noqa: E402
from src.plugins import mongo_claves, mongo_telegram as tg   # noqa: E402
from src.mcp.tools.busqueda import service as busq   # noqa: E402

al._archivo = lambda: Path(os.environ.get("TEMP", "/tmp")) / "mongo_alarmas_prueba.json"
al._cargado, al._items = True, []
mostradas = []
from src.plugins import mongo_caras                  # noqa: E402
mongo_caras.mostrar = lambda n, *a, **k: mostradas.append(n) or True

bien = mal = 0


def ver(nombre, valor, esperado):
    global bien, mal
    ok = esperado(valor) if callable(esperado) else valor == esperado
    bien += ok
    mal += not ok
    print(f"{'ok   ' if ok else 'FALLA'} {nombre}: {valor!r}")


ver("ayuda", tg.responder("/ayuda").startswith("Soy MongoBot"), True)
ver("alarma 6:30", tg.responder("/alarma 6:30 levantarse"), lambda r: r.startswith("Listo: #1 alarma") and "levantarse" in r)
ver("recordar 7 pm", tg.responder("/recordar 7 pm sacar la basura"), lambda r: "recordatorio" in r and "19:00" in r)
ver("recordar sin texto", tg.responder("/recordar 18:00"), lambda r: r.startswith("Decime qué"))
ver("temporizador 10m", tg.responder("/temporizador 10m arroz"), lambda r: "temporizador" in r and "arroz" in r)
ver("temporizador con hora", tg.responder("/temporizador 6:30"), lambda r: "cuánto tiempo" in r)
ver("hora mala", tg.responder("/alarma 25:99"), lambda r: r.startswith("No entendí"))
ver("lista", tg.responder("/lista").count("\n"), 2)
ver("cancelar 19:00", tg.responder("/cancelar 19:00"), lambda r: r.startswith("Borré") and "basura" in r)
ver("cancelar nada", tg.responder("/cancelar 3:33"), lambda r: r.startswith("No encontré"))
ver("cancelar todas", tg.responder("/cancelar todas"), lambda r: r.startswith("Borré"))
ver("lista vacía", tg.responder("/lista"), "No hay nada programado.")
ver("parar sin sonar", tg.responder("/parar"), "No estaba sonando nada.")
ver("texto suelto en pantalla", tg.responder("ya voy llegando"), "Listo, lo puse en la pantalla.")
ver("cara mensaje", mostradas[-1], "mensaje")
ver("orden rara", tg.responder("/xyz"), lambda r: r.startswith("No conozco"))
ver("orden con @bot", tg.responder("/lista@MongoBot_bot"), "No hay nada programado.")

os.environ["TAVILY_API_KEY"] = ""
r = json.loads(asyncio.run(busq.web_search({"query": "noticias Costa Rica"})))
ver("búsqueda sin clave", r["ok"] is False and "TAVILY_API_KEY" in r["error"], True)
r = json.loads(asyncio.run(busq.web_search({"query": ""})))
ver("búsqueda sin consulta", r["ok"], False)
os.environ["TAVILY_API_KEY"] = "tvly-..."
ver("clave de ejemplo no cuenta", mongo_claves.clave("TAVILY_API_KEY"), "")
os.environ["TAVILY_API_KEY"] = "tvly-abc123"
ver("clave real", mongo_claves.clave("TAVILY_API_KEY"), "tvly-abc123")

print(f"\n{bien} bien, {mal} fallas")
sys.exit(1 if mal else 0)
