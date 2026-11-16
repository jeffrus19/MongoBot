"""Herramienta MCP de búsqueda web de MongoBot: self.web.search."""

from __future__ import annotations

from collections.abc import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .service import web_search

logger = get_logger()


def register_busqueda_tools(add_tool: Callable[[McpTool], None]) -> None:
    add_tool(McpTool(
        "self.web.search",
        (
            "Search the internet (Tavily). Use it for anything current or that you may not know: news, "
            "sports results, prices, exchange rates, store hours, releases, who holds a position now, "
            "events, facts about places or people. Use it instead of answering from memory when the answer "
            "can change over time. Do NOT use it for the weather (self.weather.*) or for routes and travel "
            "times (self.traffic.check).\n"
            "Parameters:\n- query: what to search, short and specific (in Spanish or English; add "
            "'Costa Rica' when it's local).\n- max_results: 1-8 (default 5).\n"
            "Returns answer (a short summary) and results (title, url, content). Answer briefly in Spanish "
            "with what you found; mention the source name if it matters. If ok is false, say what failed."
        ),
        PropertyList([
            Property("query", PropertyType.STRING),
            Property("max_results", PropertyType.INTEGER, default_value=5, min_value=1, max_value=8),
        ]),
        web_search,
    ))
    logger.info("Registrada la herramienta MCP de búsqueda web")
