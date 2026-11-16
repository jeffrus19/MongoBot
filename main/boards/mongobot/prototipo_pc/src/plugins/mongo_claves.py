"""Claves privadas de MongoBot.

Se leen de ``mongobot_claves.json`` en la carpeta del proyecto (está en
.git/info/exclude: nunca se sube a git) o de una variable de entorno con el mismo
nombre, que tiene prioridad. Se relee cada vez, así que se pueden agregar sin
reiniciar. Un valor vacío o de ejemplo ("AIzaSy...", "tvly-...") cuenta como que no está.

    {
      "TAVILY_API_KEY": "tvly-...",
      "TELEGRAM_BOT_TOKEN": "123456:ABC...",
      "TELEGRAM_CHAT_ID": "123456789"
    }
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.logging import get_logger

logger = get_logger()

ARCHIVO = Path(__file__).resolve().parents[2] / "mongobot_claves.json"


def _de_ejemplo(valor: str) -> bool:
    return not valor or valor.endswith("...") or valor.lower() in ("pendiente", "aqui", "aquí")


def clave(nombre: str) -> str:
    """El valor de la clave, o "" si no está puesta."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        try:
            datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
            valor = str(datos.get(nombre, "") or "").strip()
        except FileNotFoundError:
            valor = ""
        except Exception as e:                                   # noqa: BLE001
            logger.warning(f"[MongoClaves] no pude leer {ARCHIVO.name}: {e}")
            valor = ""
    return "" if _de_ejemplo(valor) else valor


def asegurar_campos(nombres: list[str]) -> None:
    """Agrega al archivo los campos que falten, vacíos, para que se vea dónde van.
    No toca los valores que ya están."""
    try:
        datos = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}
        faltan = [n for n in nombres if n not in datos]
        if not faltan:
            return
        for n in faltan:
            datos[n] = ""
        ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info(f"[MongoClaves] agregué a {ARCHIVO.name}: {', '.join(faltan)}")
    except Exception as e:                                       # noqa: BLE001
        logger.warning(f"[MongoClaves] no pude actualizar {ARCHIVO.name}: {e}")
