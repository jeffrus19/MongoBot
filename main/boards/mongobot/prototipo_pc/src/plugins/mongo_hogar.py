"""Domótica: MongoBot controla la casa a través de Home Assistant (API REST).

Claves en mongobot_claves.json:
- HOME_ASSISTANT_URL: p. ej. http://192.168.1.50:8123 (o http://homeassistant.local:8123)
- HOME_ASSISTANT_TOKEN: token de acceso de larga duración (en Home Assistant: tu
  perfil > Seguridad > Tokens de acceso de larga duración > Crear token).

Los aparatos se buscan por su nombre en Home Assistant ("luz de la sala") o por su
entity_id ("light.sala"), sin importar tildes ni mayúsculas.
"""

from __future__ import annotations

from typing import Any

from src.logging import get_logger
from src.plugins import mongo_avisos, mongo_claves

logger = get_logger()

DOMINIOS = ("light", "switch", "fan", "climate", "cover", "media_player", "lock", "scene",
            "script", "input_boolean", "vacuum", "humidifier", "sensor", "binary_sensor")
CONTROLABLES = DOMINIOS[:-2]


class SinConfigurar(Exception):
    pass


def _config() -> tuple[str, str]:
    url = mongo_claves.clave("HOME_ASSISTANT_URL").rstrip("/")
    token = mongo_claves.clave("HOME_ASSISTANT_TOKEN")
    if not (url and token):
        raise SinConfigurar("falta HOME_ASSISTANT_URL o HOME_ASSISTANT_TOKEN en mongobot_claves.json")
    return url, token


def _ha(metodo: str, ruta: str, cuerpo: Any = None) -> Any:
    url, token = _config()
    return mongo_avisos.get_json(url + ruta, headers={"Authorization": f"Bearer {token}"},
                                 data=cuerpo, method=metodo, timeout=10)


def _resumen(e: dict) -> dict[str, Any]:
    a = e.get("attributes", {})
    r = {"entity_id": e["entity_id"], "name": a.get("friendly_name", e["entity_id"]), "state": e.get("state")}
    for k in ("brightness", "temperature", "current_temperature", "unit_of_measurement",
              "media_title", "current_position"):
        if k in a:
            r[k] = round(a[k] * 100 / 255) if k == "brightness" and a[k] is not None else a[k]
    if "brightness" in r:
        r["brightness_pct"] = r.pop("brightness")
    return r


def aparatos(consulta: str = "") -> list[dict]:
    estados = _ha("GET", "/api/states") or []
    q = mongo_avisos.normalizar(consulta).split()
    salida = []
    for e in estados:
        if e["entity_id"].split(".")[0] not in DOMINIOS:
            continue
        r = _resumen(e)
        texto = mongo_avisos.normalizar(f"{r['name']} {r['entity_id']}")
        if all(p in texto for p in q):
            salida.append(r)
    return salida


def buscar(objetivo: str, solo_controlables: bool = True) -> list[dict]:
    """Entidades que coinciden con el nombre o el entity_id."""
    objetivo = objetivo.strip()
    if "." in objetivo and " " not in objetivo:
        try:
            return [_resumen(_ha("GET", f"/api/states/{objetivo}"))]
        except Exception:                                        # noqa: BLE001
            pass
    vistos = aparatos(objetivo)
    if not vistos:                                   # sin palabras de relleno ("la", "de")
        palabras = [p for p in mongo_avisos.normalizar(objetivo).split()
                    if p not in ("el", "la", "los", "las", "de", "del", "en", "mi")]
        vistos = aparatos(" ".join(palabras))
    if solo_controlables:
        vistos = [v for v in vistos if v["entity_id"].split(".")[0] in CONTROLABLES]
    return vistos


def controlar(objetivo: str, accion: str, valor: float | None = None) -> dict[str, Any]:
    encontrados = buscar(objetivo)
    if not encontrados:
        return {"ok": False, "error": f"no encontré '{objetivo}' en Home Assistant"}
    if len(encontrados) > 6:
        return {"ok": False, "error": "coinciden demasiados aparatos; sé más específico",
                "matches": [e["name"] for e in encontrados[:10]]}
    hechos = []
    for e in encontrados:
        dominio = e["entity_id"].split(".")[0]
        servicio, datos = _servicio(dominio, accion, valor)
        if servicio is None:
            return {"ok": False, "error": f"'{accion}' no aplica a {e['name']} ({dominio})"}
        _ha("POST", f"/api/services/{servicio}", {"entity_id": e["entity_id"], **datos})
        hechos.append(e["name"])
    logger.info(f"[MongoHogar] {accion} {valor if valor is not None else ''} -> {', '.join(hechos)}")
    return {"ok": True, "action": accion, "devices": hechos}


def _servicio(dominio: str, accion: str, valor: float | None) -> tuple[str | None, dict]:
    a = accion.lower()
    if dominio in ("scene", "script"):
        return f"{dominio}/turn_on", {}
    if a in ("turn_on", "on", "encender", "prender"):
        return f"{dominio}/turn_on" if dominio != "cover" else "cover/open_cover", {}
    if a in ("turn_off", "off", "apagar"):
        return f"{dominio}/turn_off" if dominio != "cover" else "cover/close_cover", {}
    if a in ("toggle", "cambiar"):
        return f"{dominio}/toggle", {}
    if a in ("open", "abrir") and dominio == "cover":
        return "cover/open_cover", {}
    if a in ("close", "cerrar") and dominio == "cover":
        return "cover/close_cover", {}
    if a in ("lock", "cerrar") and dominio == "lock":
        return "lock/lock", {}
    if a in ("unlock", "abrir") and dominio == "lock":
        return "lock/unlock", {}
    if a in ("brightness", "set_brightness", "brillo") and dominio == "light" and valor is not None:
        return "light/turn_on", {"brightness_pct": max(0, min(100, int(valor)))}
    if a in ("temperature", "set_temperature", "temperatura") and dominio == "climate" and valor is not None:
        return "climate/set_temperature", {"temperature": valor}
    if a in ("volume", "volumen") and dominio == "media_player" and valor is not None:
        return "media_player/volume_set", {"volume_level": max(0.0, min(1.0, valor / 100))}
    if a in ("play_pause", "pausa", "play") and dominio == "media_player":
        return "media_player/media_play_pause", {}
    return None, {}
