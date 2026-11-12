"""Clima real con Open-Meteo (gratis, sin clave). Reemplaza los datos de prueba
que traía py-xiaozhi (siempre "Pekín, 25 °C, despejado").

MongoBot: además de devolver el clima, pone la cara de sol, nube o lluvia.
Si no hay internet, devuelve un error claro en vez de inventar datos.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from typing import Any

from src.logging import get_logger

logger = get_logger()

CIUDAD_POR_DEFECTO = "San José, Costa Rica"
_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_CLIMA = "https://api.open-meteo.com/v1/forecast"

# códigos WMO de Open-Meteo -> (descripción, cara)
_CODIGOS = {
    0: ("despejado", "clima_sol"), 1: ("mayormente despejado", "clima_sol"),
    2: ("parcialmente nublado", "clima_nube"), 3: ("nublado", "clima_nube"),
    45: ("neblina", "clima_nube"), 48: ("neblina con escarcha", "clima_nube"),
    51: ("llovizna débil", "clima_lluvia"), 53: ("llovizna", "clima_lluvia"), 55: ("llovizna fuerte", "clima_lluvia"),
    56: ("llovizna helada", "clima_lluvia"), 57: ("llovizna helada fuerte", "clima_lluvia"),
    61: ("lluvia débil", "clima_lluvia"), 63: ("lluvia", "clima_lluvia"), 65: ("lluvia fuerte", "clima_lluvia"),
    66: ("lluvia helada", "clima_lluvia"), 67: ("lluvia helada fuerte", "clima_lluvia"),
    71: ("nieve débil", "clima_nube"), 73: ("nieve", "clima_nube"), 75: ("nieve fuerte", "clima_nube"),
    77: ("granizo fino", "clima_nube"),
    80: ("aguaceros débiles", "clima_lluvia"), 81: ("aguaceros", "clima_lluvia"), 82: ("aguaceros fuertes", "clima_lluvia"),
    85: ("chubascos de nieve", "clima_nube"), 86: ("chubascos de nieve fuertes", "clima_nube"),
    95: ("tormenta eléctrica", "clima_lluvia"), 96: ("tormenta con granizo", "clima_lluvia"),
    99: ("tormenta fuerte con granizo", "clima_lluvia"),
}


def describir_codigo(codigo: int) -> tuple[str, str]:
    return _CODIGOS.get(int(codigo), ("variable", "clima_nube"))


def _get_json(url: str, params: dict, timeout: float = 8.0) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "MongoBot/1.0 (py-xiaozhi)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _ubicar(ciudad: str) -> dict:
    """Nombre de ciudad -> {nombre, pais, lat, lon}. Prueba también sin el país."""
    nombre = ciudad.strip() or CIUDAD_POR_DEFECTO
    intentos = [nombre]
    if "," in nombre:
        intentos.append(nombre.split(",")[0].strip())
    for q in intentos:
        datos = _get_json(_GEO, {"name": q, "count": 5, "language": "es", "format": "json"})
        res = datos.get("results") or []
        if not res:
            continue
        # si se mencionó Costa Rica (o no se dijo país), preferir resultados de CR
        quiere_cr = "costa rica" in nombre.lower() or "," not in nombre
        if quiere_cr:
            cr = [r for r in res if r.get("country_code") == "CR"]
            if cr:
                res = cr
        r = res[0]
        return {"nombre": r.get("name"), "pais": r.get("country"), "lat": r["latitude"], "lon": r["longitude"]}
    raise LookupError(f"no encontré la ciudad '{nombre}'")


def _clima(ciudad: str, dias: int = 0) -> dict:
    lugar = _ubicar(ciudad)
    params = {
        "latitude": lugar["lat"], "longitude": lugar["lon"], "timezone": "auto",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,precipitation",
    }
    if dias:
        params["daily"] = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        params["forecast_days"] = max(1, min(7, dias))
    datos = _get_json(_CLIMA, params)
    return {"lugar": lugar, "datos": datos}


def _mostrar_cara(cara: str) -> None:
    try:
        from src.plugins import mongo_caras

        mongo_caras.mostrar(cara, 60, hasta_respuesta=True)   # acompaña toda la respuesta
    except Exception as e:                                       # noqa: BLE001
        logger.debug(f"[WeatherTool] sin cara: {e}")


async def get_weather_payload(args: dict[str, Any]) -> str:
    ciudad = str(args.get("city") or CIUDAD_POR_DEFECTO)
    logger.info(f"[WeatherTool] clima actual de {ciudad}")
    try:
        r = await asyncio.to_thread(_clima, ciudad)
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[WeatherTool] no pude obtener el clima: {e}")
        return json.dumps({"ok": False, "error": f"could not get the weather: {e}"}, ensure_ascii=False)
    c = r["datos"].get("current", {})
    desc, cara = describir_codigo(c.get("weather_code", 3))
    _mostrar_cara(cara)
    return json.dumps({
        "ok": True, "city": r["lugar"]["nombre"], "country": r["lugar"]["pais"],
        "condition": desc, "temperature_c": c.get("temperature_2m"), "feels_like_c": c.get("apparent_temperature"),
        "humidity_pct": c.get("relative_humidity_2m"), "wind_kmh": c.get("wind_speed_10m"),
        "precipitation_mm": c.get("precipitation"), "time": c.get("time"), "source": "Open-Meteo",
    }, ensure_ascii=False)


async def get_forecast_payload(args: dict[str, Any]) -> str:
    ciudad = str(args.get("city") or CIUDAD_POR_DEFECTO)
    dias = int(args.get("days", 3))
    logger.info(f"[WeatherTool] pronóstico de {dias} días para {ciudad}")
    try:
        r = await asyncio.to_thread(_clima, ciudad, dias)
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[WeatherTool] no pude obtener el pronóstico: {e}")
        return json.dumps({"ok": False, "error": f"could not get the forecast: {e}"}, ensure_ascii=False)
    d = r["datos"].get("daily", {})
    dias_lista = []
    for i, fecha in enumerate(d.get("time", [])):
        desc, cara = describir_codigo(d["weather_code"][i])
        dias_lista.append({"date": fecha, "condition": desc, "max_c": d["temperature_2m_max"][i],
                           "min_c": d["temperature_2m_min"][i],
                           "rain_probability_pct": (d.get("precipitation_probability_max") or [None] * 9)[i]})
    if dias_lista:
        _mostrar_cara(describir_codigo(d["weather_code"][0])[1])
    return json.dumps({"ok": True, "city": r["lugar"]["nombre"], "country": r["lugar"]["pais"],
                       "forecast": dias_lista, "source": "Open-Meteo"}, ensure_ascii=False)
