"""Rutas y tiempo de viaje para MongoBot, sin claves: OpenStreetMap.

- Nominatim (nominatim.openstreetmap.org) convierte el nombre del lugar en coordenadas.
- OSRM (router.project-osrm.org) calcula la ruta en carro y el tiempo.

No hay tráfico en vivo: el tiempo es el de una calle sin presa (en hora pico puede ser
bastante más). Los dos servicios son públicos y gratuitos; piden un User-Agent que
identifique la aplicación y no más de una consulta por segundo, de sobra para MongoBot.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.logging import get_logger

logger = get_logger()

ORIGEN_POR_DEFECTO = "Sabanilla, Montes de Oca, San José, Costa Rica"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_OSRM = "https://router.project-osrm.org/route/v1/driving/"
_UA = "MongoBot/1.0 (asistente de voz personal; py-xiaozhi)"
_ultima_consulta = 0.0


def _get_json(url: str, params: dict, timeout: float = 10.0) -> Any:
    global _ultima_consulta
    espera = 1.05 - (time.monotonic() - _ultima_consulta)     # máximo 1 consulta por segundo
    if espera > 0:
        time.sleep(espera)
    _ultima_consulta = time.monotonic()
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": _UA, "Accept-Language": "es"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"el servicio respondió {e.code}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"sin conexión ({e.reason})") from None


def ubicar(lugar: str) -> dict:
    """Nombre de lugar -> {nombre, lat, lon}. Prefiere Costa Rica."""
    for q, extra in ((lugar, {"countrycodes": "cr"}), (lugar, {})):
        datos = _get_json(_NOMINATIM, {"q": q, "format": "jsonv2", "limit": 1, **extra})
        if datos:
            d = datos[0]
            return {"nombre": d.get("name") or d.get("display_name", lugar).split(",")[0],
                    "lat": float(d["lat"]), "lon": float(d["lon"])}
    raise LookupError(f"no encontré '{lugar}'")


def _ruta(o: dict, d: dict) -> dict:
    coords = f"{o['lon']},{o['lat']};{d['lon']},{d['lat']}"
    return _get_json(_OSRM + coords, {"overview": "false", "alternatives": "true", "steps": "true"})


def resumir(datos: dict, origen: str, destino: str) -> dict:
    rutas = datos.get("routes") or [] if datos.get("code", "Ok") == "Ok" else []
    if not rutas:
        return {"ok": False, "error": f"no route found from '{origen}' to '{destino}'"}
    lista = []
    for r in rutas:
        via = ", ".join(x for x in (leg.get("summary", "") for leg in r.get("legs", [])) if x)
        lista.append({"via": via, "minutes_without_traffic": round(r.get("duration", 0) / 60),
                      "distance_km": round(r.get("distance", 0) / 1000, 1)})
    mejor = min(lista, key=lambda x: x["minutes_without_traffic"])
    return {"ok": True, "origin": origen, "destination": destino, "live_traffic": False,
            "best": mejor, "alternatives": [x for x in lista if x is not mejor],
            "note": "Estimated time with no traffic (OpenStreetMap). At rush hour it can take much longer."}


def _consultar(origen: str, destino: str) -> dict:
    o, d = ubicar(origen), ubicar(destino)
    return resumir(_ruta(o, d), o["nombre"] if origen != ORIGEN_POR_DEFECTO else "Sabanilla", d["nombre"])


async def check_traffic(args: dict[str, Any]) -> str:
    destino = str(args.get("destination", "")).strip()
    origen = str(args.get("origin", "")).strip() or ORIGEN_POR_DEFECTO
    if not destino:
        return json.dumps({"ok": False, "error": "destination is required"}, ensure_ascii=False)
    try:
        resultado = await asyncio.to_thread(_consultar, origen, destino)
    except LookupError as e:
        resultado = {"ok": False, "error": f"could not find the place: {e}"}
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[Trafico] no pude consultar: {e}")
        resultado = {"ok": False, "error": f"could not get the route: {e}"}
    logger.info(f"[Trafico] {origen} -> {destino}: {resultado}")
    return json.dumps(resultado, ensure_ascii=False)
