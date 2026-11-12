"""Herramienta MCP de tráfico de MongoBot: self.traffic.check."""

from __future__ import annotations

from collections.abc import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .service import ORIGEN_POR_DEFECTO, check_traffic

logger = get_logger()


def register_trafico_tools(add_tool: Callable[[McpTool], None]) -> None:
    tool = McpTool(
        "self.traffic.check",
        (
            "Check LIVE traffic and driving time between two places (Google Maps, real-time traffic). "
            "Use it for '¿cómo está el tráfico a Escazú?', '¿cuánto duro de Sabanilla a Heredia?', "
            "'¿hay presa para ir al aeropuerto?'. Any destination works: a town, an address, a mall, "
            "a business. Add ', Costa Rica' if the place is ambiguous.\n"
            f"Parameters:\n- destination: where the user wants to go (required).\n"
            f"- origin: where they leave from; leave empty for home ({ORIGEN_POR_DEFECTO}).\n"
            "Returns the best route (via, minutes with and without traffic, delay, km and a traffic level: "
            "fluido, moderado, pesado or muy pesado) and the alternatives. Answer briefly in Spanish: the "
            "time with traffic, how bad it is, the road it goes by and, if an alternative is not much slower, "
            "mention it. If ok is false, say what failed."
        ),
        PropertyList([
            Property("destination", PropertyType.STRING),
            Property("origin", PropertyType.STRING, default_value=""),
        ]),
        check_traffic,
    )
    add_tool(tool)
    logger.info("Registrada la herramienta MCP de tráfico")
