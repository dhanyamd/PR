<div align="center">

# 🤖 PR

### AI-powered Pull Request reviewer that automatically reviews code, checks Asana tasks, and posts structured feedback to Slack — the moment a PR is opened.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-AI_Engine-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-FF6B6B?style=for-the-badge)](https://modelcontextprotocol.io)
[![Slack](https://img.shields.io/badge/Slack-Notifications-4A154B?style=for-the-badge&logo=slack&logoColor=white)](https://slack.com)

</div>

---

## ✨ What It Does

Every time a Pull Request is **opened, reopened, or updated** on GitHub, PR Agent:

1. 📥 **Receives the webhook** from GitHub via ngrok
2. 🔍 **Fetches the PR diff and files** using the GitHub REST API
3. 🔗 **Extracts the linked Asana task** from the PR title/description
4. ✅ **Checks requirements** — does the code actually implement what the task asked for?
5. 💬 **Posts a structured review** directly to your Slack channel

> No manual reviews triggered. No copy-paste. Fully automated.

---

## 🏗️ Architecture

```
GitHub PR Event
      │
      ▼
  ngrok tunnel
      │
      ▼
┌─────────────────────────────────────────┐
│         MCP Host  (port 5001)           │
│                                         │
│  FastAPI Webhook  ──►  MCPHost          │
│                         │               │
│              Gemini 2.5 Flash           │
│              (with retry + backoff)     │
└───────────────┬─────────────────────────┘
                │  MCP (Streamable HTTP)
                ▼
┌─────────────────────────────────────────┐
│        MCP Server  (port 8000)          │
│                                         │
│  ┌───────────┐  ┌───────┐  ┌────────┐  │
│  │  GitHub   │  │ Slack │  │ Asana  │  │
│  │ REST API  │  │  Bot  │  │  API   │  │
│  └───────────┘  └───────┘  └────────┘  │
└─────────────────────────────────────────┘
                │
                ▼
         Opik Observability
         (traces every LLM call)
```

---

## 📦 Project Structure

```
PR/
├── apps/
│   ├── mcp_server/              # Tool registry (FastMCP)
│   │   └── src/
│   │       ├── main.py          # Server entrypoint (port 8000)
│   │       ├── config.py        # Settings & env vars
│   │       └── servers/
│   │           ├── tool_registry.py     # Registers all tools
│   │           ├── github_server.py     # GitHub REST API tools
│   │           ├── slack_server.py      # Slack messaging tools
│   │           ├── asana_server.py      # Asana task tools
│   │           ├── prompts.py           # Versioned PR review prompt
│   │           └── agent_scope_server.py
│   │
│   └── mcp_host/                # Webhook listener + AI orchestrator
│       └── src/mcp_host/
│           ├── api/
│           │   └── webhook.py           # FastAPI webhook endpoint
│           ├── host/
│           │   ├── host.py              # Gemini orchestrator + retry logic
│           │   └── connection_manager.py # MCP session management
│           ├── config/
│           │   └── settings.py          # Pydantic settings
│           └── utils/
│               ├── opik_utils.py        # Observability helpers
│               └── mcp_compat.py        # MCP result serialization
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) package manager
- [`ngrok`](https://ngrok.com) for exposing localhost
- A GitHub repo with a configured webhook
- Slack App with `chat:write` bot permission
- Asana Personal Access Token
- Google Gemini API Key

---

### 1. Clone & Configure

```bash
git clone https://github.com/dhanyamd/PR.git
cd PR
```

Create `apps/mcp_server/.env` and `apps/mcp_host/.env` with:

```env
# GitHub
GITHUB_CLIENT_ID="your_github_client_id"
GITHUB_CLIENT_SECRET="your_github_client_secret"
GITHUB_ACCESS_TOKEN="ghp_your_token_here"
GITHUB_WEBHOOK_SECRET="your_optional_webhook_secret"

# Slack
SLACK_BOT_TOKEN="xoxb-your-bot-token"
SLACK_CHANNEL_ID="C0XXXXXXXX"

# Asana
ASANA_TOKEN="your_asana_pat"
ASANA_PROJECT_GID="your_project_gid"

# Gemini
GEMINI_API_KEY="your_gemini_api_key"

# Opik Observability
OPIK_API_KEY="your_opik_key"
OPIK_PROJECT="your_project_name"

# Internal
TOOL_REGISTRY_URL="http://localhost:8000/mcp"
```

---

### 2. Start the MCP Server (Tool Registry)

```bash
cd apps/mcp_host
uv run python ../mcp_server/src/main.py
```

Runs on **`http://localhost:8000/mcp`** — serves GitHub, Slack, and Asana tools over MCP.

---

### 3. Start the Webhook Host

```bash
cd apps/mcp_host
PYTHONPATH=src/mcp_host uv run python -m api.webhook
```

Runs on **`http://localhost:5001`** — listens for incoming GitHub webhook events.

---

### 4. Expose with ngrok

```bash
ngrok http 5001
```

Copy the HTTPS URL (e.g. `https://xxxx.ngrok-free.dev`) for the next step.

---

### 5. Configure GitHub Webhook

Go to your repo → **Settings → Webhooks → Add webhook**:

| Field | Value |
|---|---|
| **Payload URL** | `https://xxxx.ngrok-free.dev/webhook` |
| **Content type** | `application/json` |
| **Events** | Pull requests ✅ |
| **Active** | ✅ |

---

### 6. Open a Pull Request 🎉

Create a PR on your repo. Within seconds you'll receive a structured review in Slack like:

```
🔍 Pull Request Review

PR URL: https://github.com/org/repo/pull/42

📋 Summary:
Adds retry logic with exponential backoff to all LLM and tool calls,
preventing transient API errors from failing PR reviews silently.

🎯 Asana Task: FFM-42
Task: "Add resilience to AI pipeline"
Status: In Progress ✅ Requirements matched.

📌 Requirement Check:
The implementation covers all acceptance criteria — retry wrapper,
configurable delays, and logging on each failed attempt.

💡 Improvement Suggestions:
1. Add a unit test for the _with_retry() helper
2. Consider making MAX_RETRIES configurable via env var
3. Log the total retry duration for observability dashboards
```

---

## 🛠️ Key Features

| Feature | Details |
|---|---|
| **Automatic PR reviews** | Triggers on `opened`, `reopened`, `synchronize` |
| **GitHub REST API** | Fetches PR diff, files, and metadata directly |
| **Asana integration** | Extracts task IDs from PR titles, validates requirements |
| **Slack notifications** | Posts structured review to any channel |
| **Retry with backoff** | Exponential backoff on all LLM and tool calls |
| **Webhook security** | HMAC-SHA256 signature verification |
| **Opik observability** | Every LLM call and tool call is traced |
| **Versioned prompts** | Prompts managed through Opik for A/B testing |
| **MCP architecture** | Tools exposed over Model Context Protocol |

---

## 🔍 Observability

All LLM calls and tool invocations are traced via **[Opik](https://www.comet.com/opik)**. View traces at [comet.com](https://www.comet.com) under your configured project.

Each review creates a full trace including:
- System prompt generation
- Gemini calls with token counts  
- GitHub / Slack / Asana tool calls
- Final response text

---

## 🔒 Security

Webhook payloads are verified using **GitHub's HMAC-SHA256 signature** (`X-Hub-Signature-256`). Set `GITHUB_WEBHOOK_SECRET` in your `.env` to enable verification. Without it, the server runs in dev mode and logs a warning.

---

## 🤝 Contributing

PRs welcome! The agent will automatically review your contribution 😄

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes with a meaningful message
4. Push and open a PR — the agent will review it!

---

<div align="center">

Built with ❤️ using **Gemini 2.5 Flash**, **FastMCP**, **FastAPI**, and **Opik**

</div>
