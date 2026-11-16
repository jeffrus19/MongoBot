"""Memoria personal de MongoBot: cosas que le pedís que recuerde.

"Mongo, acordate que las llaves del carro están en la gaveta del escritorio" y
después "¿dónde dejé las llaves del carro?". Se guarda en mongo_memoria.json en la
carpeta de datos de py-xiaozhi (solo en tu compu).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from src.logging import get_logger
from src.plugins.mongo_avisos import normalizar

logger = get_logger()

VACIAS = set("""a al algo como con cual cuando de del donde dónde el ella en es esta está estan están
eso esta este fue la las le lo los me mi mis muy no o para pero por que qué se si sí su sus te tengo
tu un una uno y ya yo acordate acuerdate recorda recordá recuerda recuerdas dije deje dejé puse guarde
guardé""".split())
_items: list[dict] | None = None


def _archivo() -> Path:
    from src.utils.resource_finder import get_user_data_dir

    return get_user_data_dir() / "mongo_memoria.json"


def _cargar() -> list[dict]:
    global _items
    if _items is None:
        try:
            _items = json.loads(_archivo().read_text(encoding="utf-8"))
        except FileNotFoundError:
            _items = []
        except Exception as e:                                   # noqa: BLE001
            logger.error(f"[MongoMemoria] no pude leer la memoria: {e}")
            _items = []
    return _items


def _guardar() -> None:
    p = _archivo()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_items, ensure_ascii=False, indent=2), encoding="utf-8")


def _palabras(texto: str) -> set[str]:
    ps = {p for p in re.findall(r"[a-z0-9ñ]+", normalizar(texto)) if p not in VACIAS and len(p) > 1}
    # plural sencillo: "llaves" ~ "llave"
    return ps | {p[:-1] for p in ps if p.endswith("s") and len(p) > 3}


def recordar(texto: str) -> dict:
    items = _cargar()
    texto = texto.strip()
    nuevo = {"id": max([i["id"] for i in items], default=0) + 1, "texto": texto,
             "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")}
    items.append(nuevo)
    _guardar()
    logger.info(f"[MongoMemoria] recordé #{nuevo['id']}: {texto}")
    return nuevo


def buscar(consulta: str, maximo: int = 5) -> list[dict]:
    items = _cargar()
    q = _palabras(consulta)
    if not q:
        return list(reversed(items))[:maximo]
    puntuados = []
    for it in items:
        comunes = len(q & _palabras(it["texto"]))
        if comunes:
            puntuados.append((comunes, it["id"], it))
    puntuados.sort(key=lambda x: (-x[0], -x[1]))      # más palabras en común; a igual, lo más nuevo
    return [it for _, _, it in puntuados[:maximo]]


def olvidar(cual: str) -> list[dict]:
    global _items
    items = _cargar()
    c = cual.strip().lstrip("#")
    if c.isdigit():
        quitados = [i for i in items if str(i["id"]) == c]
    else:
        quitados = buscar(c, maximo=1) if c else []
    _items = [i for i in items if i not in quitados]
    _guardar()
    return quitados


def todo() -> list[dict]:
    return list(_cargar())
