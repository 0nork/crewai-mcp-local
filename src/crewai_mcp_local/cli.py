"""
0nmcp-crewai-local — local self-hosted MCP server for the crewAI OSS library.

Exposes one primary tool: ``crew_run``. The caller passes a JSON crew
config (agents + tasks + process) plus inputs. The server constructs a
crewAI ``Crew``, runs it locally, and returns the result.

This is the unlimited / no-quota path — counterpart to the Enterprise-API
wrapper (``0nmcp-crewai`` on npm).

Run via stdio MCP transport:

    pipx install 0nmcp-crewai-local
    crewai-mcp-local

Or via uvx / pipx ephemeral:

    uvx 0nmcp-crewai-local

Env (optional):
    CREWAI_LLM_MODEL          — default LLM model (e.g. 'gpt-4o-mini')
    CREWAI_LLM_BASE_URL       — for local Ollama / custom endpoint
    OPENAI_API_KEY            — most agents need this set
    GROQ_API_KEY              — alternative if Groq is the model provider

The OSS library reads model config from env or per-agent. We pass through.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger("crewai-mcp-local")

CREW_RUN_SCHEMA = {
    "type": "object",
    "properties": {
        "agents": {
            "type": "array",
            "description": (
                "Crew agents. Each agent: {role, goal, backstory, llm?, "
                "verbose?, allow_delegation?, tools?}. tools is a list of "
                "tool names from crewai_tools (e.g. ['SerperDevTool'])."
            ),
            "items": {"type": "object"},
        },
        "tasks": {
            "type": "array",
            "description": (
                "Crew tasks. Each task: {description, expected_output, "
                "agent_index, context_indices?}. agent_index references the "
                "agents array (0-based). context_indices reference earlier "
                "tasks whose outputs feed in."
            ),
            "items": {"type": "object"},
        },
        "process": {
            "type": "string",
            "enum": ["sequential", "hierarchical"],
            "default": "sequential",
        },
        "inputs": {
            "type": "object",
            "description": "Variables interpolated into agent/task strings via {var_name}.",
        },
        "verbose": {"type": "boolean", "default": False},
        "memory": {"type": "boolean", "default": False},
        "max_rpm": {"type": "integer", "description": "Max requests/min across the crew."},
    },
    "required": ["agents", "tasks"],
}


def _build_tool(name: str | None, llm: Any) -> Any | None:
    """Resolve a tool name to a crewai_tools class. Returns None if not found."""
    if not name:
        return None
    try:
        import crewai_tools  # noqa: WPS433  (optional dependency)

        cls = getattr(crewai_tools, name, None)
        if cls is None:
            return None
        # Most tools take no args; some take llm — try both.
        try:
            return cls()
        except TypeError:
            return cls(llm=llm)
    except ImportError:
        return None


def _run_crew(args: dict[str, Any]) -> dict[str, Any]:
    """Build + run a crewAI Crew from the provided config."""
    from crewai import Agent, Crew, Process, Task

    agent_configs = args.get("agents") or []
    task_configs = args.get("tasks") or []
    if not agent_configs:
        raise ValueError("agents is required and must be non-empty")
    if not task_configs:
        raise ValueError("tasks is required and must be non-empty")

    # Build agents
    agents: list[Agent] = []
    for ac in agent_configs:
        kwargs: dict[str, Any] = {
            "role": ac.get("role", ""),
            "goal": ac.get("goal", ""),
            "backstory": ac.get("backstory", ""),
            "verbose": bool(ac.get("verbose", False)),
            "allow_delegation": bool(ac.get("allow_delegation", False)),
        }
        if ac.get("llm"):
            kwargs["llm"] = ac["llm"]

        tools_in = ac.get("tools") or []
        resolved_tools = [t for t in (_build_tool(name, kwargs.get("llm")) for name in tools_in) if t]
        if resolved_tools:
            kwargs["tools"] = resolved_tools

        agents.append(Agent(**kwargs))

    # Build tasks
    tasks: list[Task] = []
    for tc in task_configs:
        idx = int(tc.get("agent_index", 0))
        if idx < 0 or idx >= len(agents):
            raise ValueError(f"task agent_index {idx} out of range")

        kwargs = {
            "description": tc.get("description", ""),
            "expected_output": tc.get("expected_output", ""),
            "agent": agents[idx],
        }
        ctx_idxs = tc.get("context_indices") or []
        if ctx_idxs:
            kwargs["context"] = [tasks[i] for i in ctx_idxs if 0 <= i < len(tasks)]
        tasks.append(Task(**kwargs))

    proc_name = (args.get("process") or "sequential").lower()
    process = Process.hierarchical if proc_name == "hierarchical" else Process.sequential

    crew_kwargs: dict[str, Any] = {
        "agents": agents,
        "tasks": tasks,
        "process": process,
        "verbose": bool(args.get("verbose", False)),
        "memory": bool(args.get("memory", False)),
    }
    if args.get("max_rpm"):
        crew_kwargs["max_rpm"] = int(args["max_rpm"])

    crew = Crew(**crew_kwargs)

    result = crew.kickoff(inputs=args.get("inputs") or {})

    # Normalize the result. crewAI returns CrewOutput in newer versions.
    if hasattr(result, "raw"):
        return {
            "raw": str(getattr(result, "raw", "")),
            "tasks_output": [
                {
                    "agent": getattr(t, "agent", ""),
                    "raw": str(getattr(t, "raw", "")),
                }
                for t in (getattr(result, "tasks_output", None) or [])
            ],
            "token_usage": getattr(result, "token_usage", None) and dict(result.token_usage)  # type: ignore[arg-type]
            or None,
        }
    return {"raw": str(result)}


def _agents_list_tool() -> dict[str, Any]:
    """Best-effort enumeration of crewai_tools tool classes."""
    try:
        import crewai_tools

        names = [n for n in dir(crewai_tools) if not n.startswith("_") and n.endswith("Tool")]
        return {"tools": sorted(names), "count": len(names)}
    except ImportError:
        return {"tools": [], "count": 0, "note": "crewai_tools not installed"}


async def serve() -> None:
    server = Server("0nmcp-crewai-local")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="crew_run",
                description=(
                    "Build and run a self-hosted crewAI crew locally. Pass a "
                    "JSON config of agents + tasks + (optional) inputs. "
                    "Returns the crew's final output. Unlimited — no quota. "
                    "Requires the model provider's API key in env (OPENAI_API_KEY, "
                    "GROQ_API_KEY, etc.)."
                ),
                inputSchema=CREW_RUN_SCHEMA,
            ),
            Tool(
                name="crew_list_tools",
                description=(
                    "List the crewai_tools tool classes available in this "
                    "environment. Useful before referencing tool names in "
                    "agent configs."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            if name == "crew_run":
                # crewAI is sync — run in a thread to avoid blocking
                result = await asyncio.to_thread(_run_crew, arguments or {})
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            if name == "crew_list_tools":
                return [TextContent(type="text", text=json.dumps(_agents_list_tool(), indent=2))]
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as exc:  # pragma: no cover — surface any failure to the client
            logger.exception("call_tool failed")
            return [TextContent(type="text", text=f"Error: {exc!s}")]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point referenced by [project.scripts]."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
