# 0nmcp-crewai-local

> An MCP server wrapping the **open-source crewAI Python library** — run unlimited self-hosted crews from any MCP client. Built by [0nORK](https://0nork.com).

[![PyPI version](https://img.shields.io/pypi/v/0nmcp-crewai-local.svg)](https://pypi.org/project/0nmcp-crewai-local/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What it does

Wraps the [crewAI](https://github.com/crewAIInc/crewAI) OSS Python library as a [Model Context Protocol](https://modelcontextprotocol.io) server. Any MCP client — Claude Code, Cursor, Windsurf, [0nMCP](https://0nmcp.com) — can now build and run crews **on your own infrastructure**, with no Enterprise quota.

Counterpart to [`0nmcp-crewai`](https://www.npmjs.com/package/0nmcp-crewai), which wraps the CrewAI Enterprise hosted API (50 free runs/month). This package is the unlimited self-hosted path.

## Tools

| Tool | Purpose |
|---|---|
| `crew_run` | Build a Crew from a JSON config (agents + tasks + process), run it locally, return the output |
| `crew_list_tools` | Enumerate the `crewai_tools` tool classes available in this environment |

## Install

### From PyPI (recommended)

```bash
pipx install 0nmcp-crewai-local
```

Or for ephemeral use:

```bash
uvx 0nmcp-crewai-local
```

### MCP client config

```json
{
  "mcpServers": {
    "crewai-local": {
      "command": "uvx",
      "args": ["0nmcp-crewai-local"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

## Usage example

Pass a complete crew config in JSON:

```jsonc
{
  "name": "crew_run",
  "arguments": {
    "agents": [
      {
        "role": "Senior Researcher",
        "goal": "Uncover the most accurate, cutting-edge information on {topic}",
        "backstory": "An expert at synthesizing technical sources into clear takeaways.",
        "verbose": true
      },
      {
        "role": "Tech Writer",
        "goal": "Turn research into a punchy 500-word brief",
        "backstory": "Writes for builders. No fluff.",
        "verbose": true
      }
    ],
    "tasks": [
      {
        "description": "Research {topic}. Identify 5 key insights.",
        "expected_output": "A bulleted list of 5 insights with sources.",
        "agent_index": 0
      },
      {
        "description": "Write a 500-word brief based on the research.",
        "expected_output": "A 500-word markdown brief.",
        "agent_index": 1,
        "context_indices": [0]
      }
    ],
    "process": "sequential",
    "inputs": { "topic": "Model Context Protocol" }
  }
}
```

## Environment variables

| Var | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | usually | crewAI agents default to OpenAI |
| `GROQ_API_KEY` | optional | Use Groq as the model provider |
| `CREWAI_LLM_MODEL` | optional | Default model name |
| `CREWAI_LLM_BASE_URL` | optional | For local Ollama or a custom endpoint |

## Why two CrewAI MCP servers?

| | This package | [`0nmcp-crewai`](https://www.npmjs.com/package/0nmcp-crewai) |
|---|---|---|
| Where crews run | Your machine / container | CrewAI Enterprise cloud |
| Quota | **Unlimited** | 50 free runs/month, paid above |
| Build crews on the fly | ✅ pass JSON config | ❌ must be pre-deployed to Enterprise |
| Best for | local dev, agencies, internal automation | hosted production runs |

Use both — `0nmcp-crewai` for quick prototyping with the free tier, `0nmcp-crewai-local` for production self-hosting.

## License

MIT — © 2026 RocketOpp LLC.

## Related

- [crewAI](https://github.com/crewAIInc/crewAI) — the OSS framework this wraps
- [0nmcp-crewai](https://www.npmjs.com/package/0nmcp-crewai) — the Enterprise API wrapper
- [0nMCP](https://www.npmjs.com/package/0nmcp) — Universal AI API Orchestrator (1,598 tools across 106 services)
- [Model Context Protocol](https://modelcontextprotocol.io) — the protocol this server implements
