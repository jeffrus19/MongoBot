"""Alarmas, temporizadores y recordatorios de MongoBot.

Las herramientas MCP (src/mcp/tools/alarmas) llaman a ``programar``, ``listar``,
``cancelar`` y ``detener``. El plugin de UI arranca ``correr`` y conecta cómo
mandarle un texto al servidor (``conectar_envio``).

Cuando llega la hora no suena un timbre: MongoBot grita "¡RING RING RING!" con su
propia voz. Para eso se le manda al servidor un aviso corto como si fuera un
mensaje ("ALARMA: gimnasio"); la descripción de las herramientas le dice al modelo
que ante esos mensajes grite "¡RING RING RING!". El servidor rechaza los avisos
largos (responde con una alerta), por eso van cortos.
La cara cambia a alarma, temporizador o recordatorio.

Si nadie la apaga, la alarma vuelve a gritar cada 30 s, hasta 3 veces. Se apaga
pidiéndoselo ("apagá la alarma") o en cuanto le hablás.

Todo se guarda en mongo_alarmas.json (carpeta de datos de py-xiaozhi), así que
sobrevive a cerrar y abrir el programa.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path

from src.logging import get_logger

logger = get_logger()

REPETIR_CADA = 30          # segundos entre gritos si nadie la apaga
VECES = 3                  # cuántas veces grita como máximo
MARCA = "[MONGO-AVISO]"    # así se reconocen los mensajes que manda el propio MongoBot

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ALIAS_DIAS = {
    "lun": 0, "lunes": 0, "mon": 0, "monday": 0,
    "mar": 1, "martes": 1, "tue": 1, "tuesday": 1,
    "mie": 2, "mié": 2, "miercoles": 2, "miércoles": 2, "wed": 2, "wednesday": 2,
    "jue": 3, "jueves": 3, "thu": 3, "thursday": 3,
    "vie": 4, "viernes": 4, "fri": 4, "friday": 4,
    "sab": 5, "sáb": 5, "sabado": 5, "sábado": 5, "sat": 5, "saturday": 5,
    "dom": 6, "domingo": 6, "sun": 6, "sunday": 6,
}

_enviar: Callable[[str], Awaitable[None]] | None = None
_items: list[dict] = []
_cargado = False
_sonando: dict | None = None      # {"item": ..., "veces": n, "ultimo": t}


# ---------------------------------------------------------------- guardar / cargar

def _archivo() -> Path:
    from src.utils.resource_finder import get_user_data_dir

    return get_user_data_dir() / "mongo_alarmas.json"


def _cargar() -> None:
    global _items, _cargado
    _cargado = True
    try:
        p = _archivo()
        if p.exists():
            _items = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        logger.error(f"[MongoAlarmas] no pude leer las alarmas: {e}")
        _items = []


def _guardar() -> None:
    try:
        p = _archivo()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:                                       # noqa: BLE001
        logger.error(f"[MongoAlarmas] no pude guardar las alarmas: {e}")


def _asegurar() -> None:
    if not _cargado:
        _cargar()


# ---------------------------------------------------------------- fechas

def leer_dias(texto: str) -> list[int]:
    """'' -> una sola vez; 'diario', 'lun-vie', 'fin de semana', 'lun,mie,vie'..."""
    t = (texto or "").strip().lower()
    if not t or t in ("una vez", "once", "no"):
        return []
    if t in ("diario", "todos", "todos los dias", "todos los días", "daily", "everyday", "cada dia", "cada día"):
        return list(range(7))
    if t in ("lun-vie", "entre semana", "semana", "weekdays", "lunes a viernes", "de lunes a viernes"):
        return [0, 1, 2, 3, 4]
    if t in ("fin de semana", "fines de semana", "weekend", "sab-dom", "sábado y domingo", "sabado y domingo"):
        return [5, 6]
    if "-" in t and "," not in t:
        a, b = [x.strip() for x in t.split("-", 1)]
        if a in _ALIAS_DIAS and b in _ALIAS_DIAS:
            i, j = _ALIAS_DIAS[a], _ALIAS_DIAS[b]
            return list(range(i, j + 1)) if i <= j else list(range(i, 7)) + list(range(0, j + 1))
    dias = []
    for parte in t.replace(" y ", ",").replace(" ", ",").split(","):
        parte = parte.strip()
        if parte in _ALIAS_DIAS and _ALIAS_DIAS[parte] not in dias:
            dias.append(_ALIAS_DIAS[parte])
    return sorted(dias)


def leer_hora(texto: str) -> tuple[int, int]:
    """'6:30', '06:30', '18:05', '6:30 pm', '7 am'."""
    t = texto.strip().lower().replace(".", "").replace(" ", "")
    pm = t.endswith("pm")
    am = t.endswith("am")
    t = t.replace("pm", "").replace("am", "")
    if ":" in t:
        h, m = t.split(":", 1)
        h, m = int(h), int(m)
    else:
        h, m = int(t), 0
    if pm and h < 12:
        h += 12
    if am and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("hora fuera de rango")
    return h, m


def proxima(h: int, m: int, dias: list[int], desde: datetime | None = None) -> datetime:
    ahora = desde or datetime.now()
    for d in range(8):
        cand = (ahora + timedelta(days=d)).replace(hour=h, minute=m, second=0, microsecond=0)
        if cand <= ahora:
            continue
        if not dias or cand.weekday() in dias:
            return cand
    return ahora + timedelta(days=1)


def describir(it: dict) -> str:
    cuando = datetime.fromtimestamp(it["proxima"]).strftime("%d/%m %H:%M")
    rep = ""
    if it.get("dias"):
        rep = " (se repite: " + ", ".join(DIAS[d] for d in it["dias"]) + ")"
    texto = f" – {it['texto']}" if it.get("texto") else ""
    return f"#{it['id']} {it['tipo']} {cuando}{rep}{texto}"


# ---------------------------------------------------------------- lo que usan las herramientas

def programar(tipo: str, cuando: datetime, texto: str = "", dias: list[int] | None = None,
              hora: tuple[int, int] | None = None) -> dict:
    _asegurar()
    nuevo_id = max([it["id"] for it in _items], default=0) + 1
    it = {"id": nuevo_id, "tipo": tipo, "proxima": cuando.timestamp(), "texto": texto,
          "dias": dias or [], "hora": list(hora) if hora else None}
    _items.append(it)
    _guardar()
    logger.info(f"[MongoAlarmas] programada {describir(it)}")
    return it


def listar() -> list[dict]:
    _asegurar()
    return sorted(_items, key=lambda it: it["proxima"])


def cancelar(cual: str) -> list[dict]:
    """'all' / 'todas' borra todo; si no, por número de id."""
    global _items
    _asegurar()
    c = str(cual).strip().lower().lstrip("#")
    if c in ("all", "todas", "todo", "todos"):
        quitadas, _items = _items, []
    else:
        quitadas = [it for it in _items if str(it["id"]) == c]
        _items = [it for it in _items if str(it["id"]) != c]
    _guardar()
    return quitadas


def detener() -> bool:
    """Calla la alarma que esté sonando."""
    global _sonando
    estaba = _sonando is not None
    _sonando = None
    if estaba:
        from src.plugins import mongo_caras

        mongo_caras.mostrar("neutral", 2)
        logger.info("[MongoAlarmas] alarma apagada")
    return estaba


def usuario_hablo(texto: str) -> None:
    """Si el usuario le habla mientras grita, se calla (los avisos propios no cuentan)."""
    if _sonando and texto and not es_aviso_propio(texto):
        detener()


def conectar_envio(fn: Callable[[str], Awaitable[None]] | None) -> None:
    global _enviar
    _enviar = fn


# ---------------------------------------------------------------- disparar

PREFIJOS = {"alarma": "ALARMA", "temporizador": "TEMPORIZADOR", "recordatorio": "RECORDATORIO"}
LARGO_MAX = 60     # el servidor rechaza (alerta) los avisos largos: se mandan cortos


def _mensaje(it: dict, vez: int) -> str:
    """Aviso corto, p. ej. 'ALARMA: gimnasio'. La instrucción de gritar
    '¡RING RING RING!' está en la descripción de las herramientas self.alarm.*."""
    prefijo = PREFIJOS.get(it["tipo"], "ALARMA")
    if vez >= 2:
        prefijo += " OTRA VEZ"
    texto = (it.get("texto") or "").strip()
    msg = f"{prefijo}: {texto}" if texto else prefijo
    return msg[:LARGO_MAX]


def es_aviso_propio(texto: str) -> bool:
    t = (texto or "").strip().upper()
    return any(t.startswith(p) for p in PREFIJOS.values())


async def _gritar(it: dict, vez: int) -> None:
    from src.plugins import mongo_caras

    cara = {"alarma": "alarma", "temporizador": "temporizador", "recordatorio": "recordatorio"}.get(it["tipo"], "alarma")
    mongo_caras.mostrar(cara if it["tipo"] != "temporizador" else "alarma", REPETIR_CADA + 2)
    if _enviar is None:
        logger.warning("[MongoAlarmas] no hay conexión con el servidor para gritar")
        return
    try:
        await _enviar(_mensaje(it, vez))
    except Exception as e:                                       # noqa: BLE001
        logger.error(f"[MongoAlarmas] no pude mandar el aviso: {e}")


async def _revisar() -> None:
    global _sonando
    _asegurar()
    ahora = time.time()
    # ¿le toca volver a gritar a la que está sonando?
    if _sonando and ahora - _sonando["ultimo"] >= REPETIR_CADA:
        if _sonando["veces"] >= VECES:
            logger.info("[MongoAlarmas] nadie la apagó; se calla sola")
            _sonando = None
        else:
            _sonando["veces"] += 1
            _sonando["ultimo"] = ahora
            await _gritar(_sonando["item"], _sonando["veces"])
    # ¿hay alguna que se cumplió?
    vencidas = [it for it in _items if it["proxima"] <= ahora]
    if not vencidas:
        return
    for it in vencidas:
        logger.info(f"[MongoAlarmas] ¡se cumplió! {describir(it)}")
        if it.get("dias") and it.get("hora"):
            h, m = it["hora"]
            it["proxima"] = proxima(h, m, it["dias"], datetime.fromtimestamp(ahora)).timestamp()
        else:
            _items.remove(it)
    _guardar()
    it = vencidas[0]
    _sonando = {"item": it, "veces": 1, "ultimo": ahora}
    await _gritar(it, 1)


async def correr() -> None:
    """Revisa una vez por segundo. Lo arranca el plugin de UI."""
    _asegurar()
    logger.info(f"[MongoAlarmas] revisando alarmas ({len(_items)} programadas)")
    while True:
        try:
            await _revisar()
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.error(f"[MongoAlarmas] error revisando: {e}", exc_info=True)
        await asyncio.sleep(1.0)
