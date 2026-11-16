"""Temblores: MongoBot vigila los sismos cerca de casa y avisa.

Fuente: USGS (earthquake.usgs.gov), pública y sin clave. Cubre bien los sismos
medianos y fuertes de Costa Rica; los muy pequeños los reporta mejor la Red
Sismológica Nacional u OVSICORI, que no tienen una API pública.

Avisa (cara de susto, texto en pantalla, Telegram y "¡TEMBLOR!" en voz alta) cuando:
- magnitud >= MAG_CERCA a menos de RADIO_CERCA km de casa, o
- magnitud >= MAG_LEJOS a menos de RADIO_LEJOS km.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from src.logging import get_logger
from src.plugins import mongo_avisos

logger = get_logger()

CASA = (9.946, -84.041)             # Sabanilla, Montes de Oca
MAG_CERCA, RADIO_CERCA = 4.0, 150
MAG_LEJOS, RADIO_LEJOS = 5.5, 400
REVISAR_CADA = 60                   # segundos
ANTIGUEDAD_MAX = 20 * 60            # al arrancar no avisa de los que ya pasaron hace rato
_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_hour.geojson"
_CONSULTA = "https://earthquake.usgs.gov/fdsnws/event/1/query"
_vistos: set[str] = set()


def distancia_km(lat: float, lon: float, a: tuple[float, float] = CASA) -> float:
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _sismo(f: dict) -> dict[str, Any]:
    p, (lon, lat, prof) = f["properties"], f["geometry"]["coordinates"][:3]
    cuando = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).astimezone()
    return {"id": f.get("id", ""), "magnitude": round(float(p.get("mag") or 0), 1),
            "place": p.get("place") or "", "time": cuando.strftime("%d/%m %H:%M"),
            "epoch": p["time"] / 1000, "depth_km": round(float(prof or 0)),
            "distance_km": round(distancia_km(lat, lon)), "url": p.get("url", "")}


def hay_que_avisar(s: dict) -> bool:
    return ((s["magnitude"] >= MAG_CERCA and s["distance_km"] <= RADIO_CERCA)
            or (s["magnitude"] >= MAG_LEJOS and s["distance_km"] <= RADIO_LEJOS))


def texto_aviso(s: dict) -> str:
    return (f"¡Temblor! Magnitud {s['magnitude']:.1f} a {s['distance_km']} km de casa"
            f" ({s['place']}), {s['time']}, {s['depth_km']} km de profundidad.")


def recientes(dias: int = 1, mag_min: float = 2.5, radio_km: float = 300) -> list[dict]:
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")
    datos = mongo_avisos.get_json(_CONSULTA, {
        "format": "geojson", "latitude": CASA[0], "longitude": CASA[1], "maxradiuskm": radio_km,
        "starttime": desde, "minmagnitude": mag_min, "orderby": "time", "limit": 20})
    return [_sismo(f) for f in (datos or {}).get("features", [])]


def revisar(datos: dict, ahora: float | None = None) -> list[dict]:
    """Los sismos nuevos del feed que merecen aviso (y los marca como vistos)."""
    ahora = ahora or time.time()
    nuevos = []
    for f in (datos or {}).get("features", []):
        s = _sismo(f)
        if s["id"] in _vistos:
            continue
        _vistos.add(s["id"])
        if ahora - s["epoch"] <= ANTIGUEDAD_MAX and hay_que_avisar(s):
            nuevos.append(s)
    return nuevos


async def correr() -> None:
    logger.info("[MongoTemblores] vigilando sismos cerca de casa (USGS)")
    while True:
        try:
            datos = await asyncio.to_thread(mongo_avisos.get_json, _FEED)
            for s in revisar(datos):
                mongo_avisos.avisar(texto_aviso(s), cara="shocked", segundos=20,
                                    voz=f"¡TEMBLOR! Magnitud {s['magnitude']:.1f}")
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.debug(f"[MongoTemblores] no pude revisar: {e}")
        await asyncio.sleep(REVISAR_CADA)
