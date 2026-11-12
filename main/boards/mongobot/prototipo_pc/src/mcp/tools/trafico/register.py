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
            "OpenStreetMap routes: THE default and only way to answer anything about routes, directions, "
            "distances, travel times or traffic. ALWAYS call it for those questions, never answer from memory "
            "and never say you can't check routes. Gives the driving route and estimated travel time between "
            "two places. It has NO live traffic: say the time is an estimate without traffic and that at rush "
            "hour it can take longer. "
            "Use it for 'ruta a Escazú', '¿cómo llego a Cartago?', '¿cuánto duro de Sabanilla a Heredia?', "
            "'¿qué tan lejos queda Limón?', '¿cómo está el tráfico a Escazú?', 'Ruta 32'. Any destination "
            "works: a town, an address, a road, a mall, a business. Add ', Costa Rica' if ambiguous.\n"
            f"Parameters:\n- destination: where the user wants to go (required).\n"
            f"- origin: where they leave from; leave empty for home ({ORIGEN_POR_DEFECTO}).\n"
            "Returns the best route (via, minutes without traffic, km) and the alternatives. Answer briefly "
            "in Spanish: the estimated time, the road it goes by and, if an alternative is close, mention it. "
            "If ok is false, say what failed."
        ),
        PropertyList([
            Property("destination", PropertyType.STRING),
            Property("origin", PropertyType.STRING, default_value=""),
        ]),
        check_traffic,
    )
    add_tool(tool)
    logger.info("Registrada la herramienta MCP de tráfico")
