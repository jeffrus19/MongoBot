import asyncio, json, os, sys
sys.path.insert(0, '.')
from src.mcp.tools.trafico import register_trafico_tools
from src.mcp.tools.trafico import service as s
t = {}; register_trafico_tools(lambda x: t.__setitem__(x.name, x)); tool = t["self.traffic.check"]
async def llamar(args):
    return json.loads(await tool.callback(tool.properties.parse_arguments(args)))
async def main():
    os.environ.pop("GOOGLE_MAPS_API_KEY", None)
    print("sin clave:", await llamar({"destination": "Escazú"}))
    os.environ["GOOGLE_MAPS_API_KEY"] = "AIza-prueba"
    pedidos = []
    def falso(o, d, k, timeout=10.0):
        pedidos.append((o, d, k))
        return {"routes": [
            {"duration": "2280s", "staticDuration": "1500s", "distanceMeters": 14300, "description": "Circunvalación"},
            {"duration": "2460s", "staticDuration": "1620s", "distanceMeters": 15800, "description": "Ruta 27"}]}
    s._pedir = falso
    r = await llamar({"destination": "Multiplaza Escazú"})
    print("con tráfico:", r); print("pedido:", pedidos[-1])
    r = await llamar({"destination": "Heredia", "origin": "Cartago"}); print("otro origen:", pedidos[-1][:2], r["best"]["traffic"])
    s._pedir = lambda *a, **k: {"routes": []}
    print("sin ruta:", await llamar({"destination": "Xyzzy"}))
    def caido(*a, **k): raise RuntimeError("Google respondió 403: API key not valid")
    s._pedir = caido
    print("clave mala:", await llamar({"destination": "Heredia"}))
    print("sin destino:", await llamar({"destination": ""}))
    for con, sin in ((100,100),(120,100),(150,100),(190,100)): print(con, sin, s.estado(con, sin))
asyncio.run(main())
