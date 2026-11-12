"""Prueba de la herramienta de rutas (OpenStreetMap), sin internet: respuestas simuladas.

Uso: python scripts/probar_trafico.py
"""
import asyncio, json, os, sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '.')
from src.mcp.tools.trafico import register_trafico_tools
from src.mcp.tools.trafico import service as s

LUGARES = {"Sabanilla": (9.94, -84.03, "Sabanilla"), "Escazú": (9.92, -84.14, "Escazú"),
           "Ruta 32, Limón": (10.0, -83.03, "Limón")}
pedidos = []
def falso(url, params, timeout=10.0):
    pedidos.append((url, params))
    if "nominatim" in url:
        for k, (lat, lon, n) in LUGARES.items():
            if params["q"].startswith(k):
                return [{"lat": str(lat), "lon": str(lon), "name": n}]
        return []
    return {"code": "Ok", "routes": [
        {"duration": 1560, "distance": 15800, "legs": [{"summary": "Circunvalación, Ruta 27"}]},
        {"duration": 1740, "distance": 14100, "legs": [{"summary": "Paseo Colón"}]}]}
s._get_json = falso
t = {}; register_trafico_tools(lambda x: t.__setitem__(x.name, x)); tool = t["self.traffic.check"]
async def llamar(a): return json.loads(await tool.callback(tool.properties.parse_arguments(a)))
async def main():
    bien = 0
    r = await llamar({"destination": "Escazú"})
    print("Sabanilla -> Escazú:", r["best"], "| alternativas:", len(r["alternatives"]), "| sin tráfico en vivo:", not r["live_traffic"])
    bien += r["ok"] and r["best"]["minutes_without_traffic"] == 26 and r["best"]["via"] == "Circunvalación, Ruta 27"
    print("pide Costa Rica primero:", pedidos[0][1].get("countrycodes") == "cr"); bien += pedidos[0][1].get("countrycodes") == "cr"
    r = await llamar({"destination": "Xyzzy"}); print("lugar que no existe:", r); bien += not r["ok"]
    r = await llamar({"destination": ""}); print("sin destino:", r); bien += not r["ok"]
    def caido(*a, **k): raise RuntimeError("sin conexión (prueba)")
    s._get_json = caido
    r = await llamar({"destination": "Escazú"}); print("sin internet:", r); bien += not r["ok"]
    print(f"\n{bien} de 5 bien")
asyncio.run(main())
