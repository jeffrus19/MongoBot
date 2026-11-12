"""Herramienta MCP para que la IA cambie la cara de MongoBot.

``self.screen.show_face``: pone cualquiera de las animaciones de assets/emojis
(las 21 emociones del servidor, las de personalidad, actividades, clima, etc.)
durante unos segundos. ``self.screen.list_faces``: devuelve la lista.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()

# Qué es cada cara, para que el modelo sepa cuál elegir.
DESCRIPCION_CARAS = (
    "Emotions: neutral, happy, laughing, funny, sad, crying, angry, loving, embarrassed, surprised, "
    "shocked, thinking, winking, cool, relaxed, delicious, kissy, confident, sleepy, silly, confused, "
    "excited, smug, terrified. "
    "Personality: rodar_ojos (eye roll, sarcasm), esceptico (skeptical), ofendido (offended, 'excuse me?'), "
    "furioso (furious, stronger than angry), eureka (lightbulb idea, found the scientific explanation), "
    "picaro (mischievous), ignorando (ignoring, looks away), orgulloso (proud), curioso (curious), "
    "aburrido (bored), decepcionado (disappointed), presumido (showing off how handsome he is, sparkles), "
    "bostezo (yawn). "
    "Activities: guitarra (plays guitar, with sound), ejercicio (push-ups), videojuego (plays a video game), "
    "leyendo (reading a book), musica (listening to music). "
    "Weather: clima_sol, clima_nube, clima_lluvia. "
    "Functions: alarma, temporizador, recordatorio, mensaje, pomodoro_trabajo, pomodoro_descanso. "
    "Seasonal: navidad (reindeer antlers), anio_nuevo (fireworks). "
    "Other: saludo (high five), llamando (taps the screen to get attention), pensando, despertar, "
    "mirando, tacto_cosquillas, tacto_molesto."
)


def register_cara_tools(add_tool: Callable[[McpTool], None]) -> None:
    from src.plugins import mongo_caras

    async def show_face(args: dict[str, Any]) -> str:
        nombre = str(args.get("face", "")).strip().lower()
        segundos = int(args.get("seconds", 8))
        disponibles = mongo_caras.caras_disponibles()
        if nombre not in disponibles:
            logger.warning(f"[CaraTools] cara desconocida: {nombre}")
            return json.dumps({"ok": False, "error": f"unknown face '{nombre}'", "available": disponibles},
                              ensure_ascii=False)
        if not mongo_caras.mostrar(nombre, segundos):
            return json.dumps({"ok": False, "error": "screen not available"}, ensure_ascii=False)
        return json.dumps({"ok": True, "face": nombre, "seconds": segundos}, ensure_ascii=False)

    async def list_faces(args: dict[str, Any]) -> str:
        return json.dumps(mongo_caras.caras_disponibles(), ensure_ascii=False)

    tools = [
        McpTool(
            "self.screen.show_face",
            (
                "Show an animated face/expression on MongoBot's screen for a few seconds. "
                "Use it when the user asks to see a face, expression, emotion or activity "
                "(e.g. 'muéstrame la cara de furioso', 'poné cara de enojado', 'tocá guitarra', "
                "'hacé ejercicio', 'mostrame la de Navidad'), and also on your own to express yourself: "
                "rodar_ojos when being sarcastic, eureka when you find the logical explanation, "
                "presumido when bragging about how handsome you are, ofendido or furioso when annoyed.\n"
                f"Available faces: {DESCRIPCION_CARAS}\n"
                "Parameters:\n"
                "- face: name of the face, exactly as listed.\n"
                "- seconds: how long to keep it (2-120, default 8; activities like guitarra look good with 20-40)."
            ),
            PropertyList([
                Property("face", PropertyType.STRING),
                Property("seconds", PropertyType.INTEGER, default_value=8, min_value=2, max_value=120),
            ]),
            show_face,
        ),
        McpTool(
            "self.screen.list_faces",
            "List the names of all animated faces MongoBot can show with self.screen.show_face.",
            PropertyList(),
            list_faces,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("Registradas %d herramientas MCP de caras", len(tools))
