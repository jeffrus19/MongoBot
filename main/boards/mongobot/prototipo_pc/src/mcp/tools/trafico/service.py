"""Tráfico en vivo con la Routes API de Google (computeRoutes, TRAFFIC_AWARE).

En Costa Rica es la única fuente con tráfico en tiempo real (TomTom y Esri no lo
tienen aquí y Waze no da API). Las primeras 5.000 consultas al mes son gratis.

La clave de API se busca, en este orden:
1. la variable de entorno GOOGLE_MAPS_API_KEY;
2. la configuración de py-xiaozhi, en MONGOBOT.GOOGLE_MAPS_API_KEY;
3. el archivo mongobot_claves.json en la carpeta de py-xiaozhi:
   {"GOOGLE_MAPS_API_KEY": "AIza..."}
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.logging import get_logger

logger = get_logger()

ORIGEN_POR_DEFECTO = "Sabanilla, Montes de Oca, San José, Costa Rica"
_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
_CAMPOS = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.description"


class SinClave(Exception):
    pass


def _clave() -> str:
    clave = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if clave:
        return clave
    try:
        from src.utils.config_manager import get_config

        clave = str(get_config().get_config("MONGOBOT.GOOGLE_MAPS_API_KEY", "") or "").strip()
        if clave:
            return clave
    except Exception:                                            # noqa: BLE001
        pass
    for carpeta in _carpetas():
        archivo = carpeta / "mongobot_claves.json"
        if archivo.is_file():
            try:
                clave = str(json.loads(archivo.read_text(encoding="utf-8")).get("GOOGLE_MAPS_API_KEY", "")).strip()
            except (OSError, ValueError) as e:
                logger.warning(f"[Trafico] no pude leer {archivo}: {e}")
            if clave.startswith("AIza"):                        # las claves de Google empiezan así
                return clave
    raise SinClave("missing Google Maps API key (GOOGLE_MAPS_API_KEY in mongobot_claves.json)")


def _carpetas() -> list[Path]:
    carpetas = [Path(__file__).resolve().parents[4]]             # raíz de py-xiaozhi
    try:
        from src.utils.resource_finder import get_app_root

        carpetas.insert(0, Path(get_app_root()))
    except Exception:                                            # noqa: BLE001
        pass
    return carpetas


def _segundos(valor: str | None) -> float:
    return float(str(valor or "0s").rstrip("s") or 0)


def _pedir(origen: str, destino: str, clave: str, timeout: float = 10.0) -> dict:
    cuerpo = {
        "origin": {"address": origen},
        "destination": {"address": destino},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": True,
        "languageCode": "es-419",
        "regionCode": "CR",
        "units": "METRIC",
    }
    req = urllib.request.Request(
        _URL, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": clave, "X-Goog-FieldMask": _CAMPOS})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:                                        # noqa: BLE001
            detalle = ""
        raise RuntimeError(f"Google respondió {e.code}: {detalle or e.reason}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"sin conexión con Google ({e.reason})") from None


def estado(con_trafico: float, sin_trafico: float) -> str:
    """fluido / moderado / pesado / muy pesado, según cuánto alarga el viaje."""
    if sin_trafico <= 0:
        return "desconocido"
    r = con_trafico / sin_trafico
    if r < 1.15:
        return "fluido"
    if r < 1.4:
        return "moderado"
    if r < 1.8:
        return "pesado"
    return "muy pesado"


def resumir(datos: dict, origen: str, destino: str) -> dict:
    rutas = datos.get("routes") or []
    if not rutas:
        return {"ok": False, "error": f"no route found from '{origen}' to '{destino}'"}
    lista = []
    for r in rutas:
        con, sin = _segundos(r.get("duration")), _segundos(r.get("staticDuration"))
        lista.append({
            "via": r.get("description", ""),
            "minutes_with_traffic": round(con / 60),
            "minutes_without_traffic": round(sin / 60),
            "delay_minutes": max(0, round((con - sin) / 60)),
            "distance_km": round(r.get("distanceMeters", 0) / 1000, 1),
            "traffic": estado(con, sin),
        })
    mejor = min(lista, key=lambda x: x["minutes_with_traffic"])
    return {"ok": True, "origin": origen, "destination": destino, "best": mejor,
            "alternatives": [x for x in lista if x is not mejor]}


async def check_traffic(args: dict[str, Any]) -> str:
    destino = str(args.get("destination", "")).strip()
    origen = str(args.get("origin", "")).strip() or ORIGEN_POR_DEFECTO
    if not destino:
        return json.dumps({"ok": False, "error": "destination is required"}, ensure_ascii=False)
    try:
        clave = _clave()
        datos = await asyncio.to_thread(_pedir, origen, destino, clave)
        resultado = resumir(datos, origen, destino)
    except SinClave as e:
        logger.warning(f"[Trafico] {e}")
        resultado = {"ok": False, "error": str(e),
                     "hint": "Tell the user the traffic function still needs the Google Maps API key."}
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[Trafico] no pude consultar: {e}")
        resultado = {"ok": False, "error": f"could not get traffic: {e}"}
    logger.info(f"[Trafico] {origen} -> {destino}: {resultado}")
    return json.dumps(resultado, ensure_ascii=False)
