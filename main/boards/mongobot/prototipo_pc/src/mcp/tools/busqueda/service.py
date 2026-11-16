"""Búsqueda en internet con Tavily (https://tavily.com), pensada para agentes de IA.

El plan gratuito trae créditos mensuales de sobra para MongoBot. La clave
(TAVILY_API_KEY, empieza con "tvly-") va en mongobot_claves.json.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from src.logging import get_logger
from src.plugins import mongo_claves

logger = get_logger()

_URL = "https://api.tavily.com/search"
MAX_RESULTADOS = 5
LARGO_EXTRACTO = 350
busquedas = 0          # cuántas veces se usó (para saber si la IA la llamó)


def _buscar(clave: str, consulta: str, max_resultados: int) -> dict[str, Any]:
    cuerpo = json.dumps({
        "query": consulta,
        "search_depth": "basic",
        "max_results": max_resultados,
        "include_answer": True,
    }).encode("utf-8")
    req = urllib.request.Request(_URL, data=cuerpo, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {clave}",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:200]
        if e.code in (401, 403):
            return {"ok": False, "error": "Tavily rechazó la clave: revisá TAVILY_API_KEY"}
        if e.code == 432 or "limit" in detalle.lower():
            return {"ok": False, "error": "se acabaron los créditos de Tavily de este mes"}
        return {"ok": False, "error": f"Tavily respondió {e.code}: {detalle}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": f"no pude conectar con Tavily: {e}"}
    resultados = [{
        "title": r.get("title", ""),
        "url": r.get("url", ""),
        "content": (r.get("content") or "")[:LARGO_EXTRACTO],
    } for r in datos.get("results", [])]
    return {"ok": True, "query": consulta, "answer": datos.get("answer") or "", "results": resultados}


async def web_search(args: dict[str, Any]) -> str:
    global busquedas
    consulta = str(args.get("query", "")).strip()
    if not consulta:
        return json.dumps({"ok": False, "error": "query is required"}, ensure_ascii=False)
    clave = mongo_claves.clave("TAVILY_API_KEY")
    if not clave:
        return json.dumps({"ok": False, "error": "falta la clave de Tavily (TAVILY_API_KEY en "
                                                 "mongobot_claves.json); no puedo buscar en internet"},
                          ensure_ascii=False)
    n = max(1, min(int(args.get("max_results", MAX_RESULTADOS) or MAX_RESULTADOS), 8))
    busquedas += 1
    logger.info(f"[MongoBusqueda] buscando: {consulta}")
    try:
        from src.plugins import mongo_caras

        mongo_caras.mostrar("pensando", 20, hasta_respuesta=True)
    except Exception:                                            # noqa: BLE001
        pass
    resultado = await asyncio.to_thread(_buscar, clave, consulta, n)
    if not resultado["ok"]:
        logger.warning(f"[MongoBusqueda] {resultado['error']}")
    return json.dumps(resultado, ensure_ascii=False)
