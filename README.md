# J-Bot

<div align="center">

## A local, extensible AI assistant for the terminal

J-Bot combines an OpenAI-compatible language model with a registry of practical
tools for files, research, calculations, memory, communication, system
inspection, and multi-step workflows.

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LLM API](https://img.shields.io/badge/LLM-OpenAI--compatible-111827?logo=openai&logoColor=white)](#llm-provider-configuration)
[![Interface](https://img.shields.io/badge/interface-Terminal%20TUI-7C3AED)](#how-it-works)
[![License](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)

</div>

<br>

> **J-Bot is a tool-using assistant, not just a chat window.**
> It decides when a capability is useful, calls the appropriate Python tool,
> incorporates the result into the conversation, and then produces a response.

---

## Contents

- [Overview](#overview)
- [What J-Bot can do](#what-j-bot-can-do)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running J-Bot](#running-j-bot)
- [Terminal commands](#terminal-commands)
- [Tool catalog](#tool-catalog)
- [Memory and persistence](#memory-and-persistence)
- [Multi-step planning](#multi-step-planning)
- [Adding a custom tool](#adding-a-custom-tool)
- [Project structure](#project-structure)
- [Data and file locations](#data-and-file-locations)
- [Security boundaries](#security-boundaries)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)
- [Current implementation status](#current-implementation-status)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

J-Bot is designed for people who want an assistant that can do more than
generate text. It can inspect files, perform calculations, search the web,
query public information, remember durable facts, interact with local system
capabilities, and coordinate several tool calls in one turn.

The project is intentionally lightweight:

- The model is accessed through an OpenAI-compatible HTTP endpoint.
- The application is written in Python.
- Tools are ordinary Python functions registered with a decorator.
- Conversation state is stored locally in JSON files.
- The primary interface is a full-screen terminal application.
- The architecture does not require a database server.

### Product model

```text
┌──────────────┐
│  User input  │
└──────┬───────┘
       │
       v
┌──────────────────────────┐
│  J-Bot terminal interface │
└──────────────┬───────────┘
               │
               v
┌──────────────────────────┐
│  Agent + conversation    │
│  history + system prompt │
└──────────────┬───────────┘
               │
               v
┌──────────────────────────┐
│  OpenAI-compatible LLM   │
└──────────────┬───────────┘
               │
       ┌───────┴────────┐
       │                │
       v                v
┌──────────────┐  ┌───────────────┐
│ Final answer  │  │ Tool call(s)  │
└──────────────┘  └───────┬───────┘
                          │
                          v
                 ┌────────────────┐
                 │ Local tool     │
                 │ execution      │
                 └───────┬────────┘
                         │
                         v
                 ┌────────────────┐
                 │ Tool result is │
                 │ sent to model  │
                 └────────────────┘
```

---

## What J-Bot can do

### Core assistant behavior

- Maintain recent conversation history across launches.
- Stream model output into the terminal.
- Call one or more tools during a single request.
- Continue reasoning after tool results are returned.
- Stop long-running work with `Ctrl+C`.
- Run an LLM-generated numbered plan step by step.
- Store durable facts separately from short-term conversation history.

### Practical work

J-Bot can help with tasks such as:

```text
Read the notes in projects/brief.txt and summarize the action items.
Calculate the return on an investment of 1200 that became 1650.
Search for the latest information about a technology and cite sources.
Remember that my preferred timezone is Africa/Lagos.
Create a CSV report from this JSON data.
Tell me the current weather in Lagos.
Inspect the available disk space on this machine.
Save this conversation as research-session.
Break this goal into steps and execute the steps one by one.
```

### Design principles

| Principle | Meaning |
|---|---|
| Local first | History, memory, sessions, and vault files are stored locally. |
| Tool aware | The model receives structured function definitions instead of guessing tool syntax. |
| Provider flexible | Any compatible `/chat/completions` endpoint can be configured. |
| Extensible | A new capability can be added as a decorated Python function. |
| Observable | Tool starts, tool results, plans, steps, errors, and cancellations appear in the UI. |
| Explicit side effects | Deletion and external actions should be reviewed carefully before use. |

---

## How it works

### 1. The terminal collects a request

The primary interface is implemented in `jbot/tui.py` using Textual. It
displays user messages, streamed assistant output, tool activity, plan steps,
status updates, and errors.

### 2. The agent builds the model context

`jbot/agent.py` creates a message list containing:

1. A system prompt describing J-Bot and its capabilities.
2. Recent user and assistant messages.
3. The new user request.
4. Durable memory facts when available.

Recent history is limited by `JBOT_HISTORY_LIMIT`, which defaults to 20
messages.

### 3. The model receives generated tool schemas

Every function decorated with `@tool` is registered in the global tool
registry. The registry inspects function signatures and docstrings to create
OpenAI-style function definitions automatically.

```python
from jbot.tools.registry import tool


@tool
def project_status(project_name: str):
    """
    Return a short status for a project.

    Args:
        project_name: The project to inspect.
    """
    return f"{project_name}: active"
```

### 4. Tool calls are normalized and executed

The LLM may return tool arguments as a JSON string or as an object. J-Bot
normalizes those arguments, performs basic type coercion, executes the matching
registered function, and appends the result as a `tool` message.

Unknown tools and tool exceptions are returned as readable errors instead of
crashing the entire session.

### 5. The loop continues until a final response

The model receives the tool result and may request another tool. The loop stops
when:

- The model returns a normal assistant response.
- `JBOT_MAX_STEPS` is reached.
- The user cancels the operation.
- The LLM request fails.

### 6. The conversation is persisted

After a completed turn, recent user and assistant messages are saved to the
configured history file. Messages falling out of the history window are passed
through the memory extraction helper so useful facts can remain available.

---

## Requirements

### Required

- Python 3.9 or newer
- `pip`
- Network access to a configured LLM provider, unless using a local provider
- An API key for a remote provider

### Installed Python packages

The main dependency set includes:

| Package | Role |
|---|---|
| `requests` | HTTP requests to LLMs and public APIs |
| `python-dotenv` | `.env` configuration loading |
| `psutil` | System and resource information |
| `yfinance` | Stock data |
| `wikipedia` | Wikipedia summaries |
| `rich` | Legacy terminal UI |
| `textual` | Primary full-screen terminal UI |
| `cryptography` | Encrypted vault support |

Some optional features import additional packages lazily. See
[Troubleshooting](#troubleshooting) if a specific feature reports a missing
module.

---

## Installation

Clone the project and enter its directory:

```bash
git clone https://github.com/novastardev/J-bot.git
cd J-bot
```

Install the declared dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the setup wizard:

```bash
python setup.py
```

The wizard can configure:

- A custom or remote OpenAI-compatible provider
- A local Ollama or LM Studio endpoint
- Optional SMTP settings for email tools
- Runtime values such as the sandbox and history limit

The wizard writes a `.env` file in the project root. Do not commit that file.

### Manual installation

If you prefer to configure the environment yourself:

```bash
cp .env.example .env
```

Edit `.env`, add the required provider settings, and start J-Bot:

```bash
python -m jbot
```

---

## Configuration

J-Bot reads environment variables through `python-dotenv`. Values in `.env`
are loaded automatically when the application starts.

### LLM provider configuration

```env
USER_LLM_API_KEY=replace-with-your-provider-key
USER_LLM_BASE_URL=https://api.example.com/v1
USER_LLM_MODEL=your-model-name
```

The client sends requests to:

```text
{USER_LLM_BASE_URL}/chat/completions
```

The endpoint should support OpenAI-style chat messages and tool calling. The
client also supports streaming responses.

### Local Ollama configuration

For an Ollama-compatible local endpoint:

```env
USER_LLM_API_KEY=local-ollama
USER_LLM_BASE_URL=http://localhost:11434/v1
USER_LLM_MODEL=llama3
```

### Local runtime settings

```env
JBOT_SANDBOX=.
JBOT_MAX_STEPS=8
JBOT_TIMEOUT=60
JBOT_TEMPERATURE=0.2
JBOT_HISTORY_LIMIT=20
```

| Variable | Default | Purpose |
|---|---:|---|
| `JBOT_SANDBOX` | Project root | Base directory for file tools and shell working directory. |
| `JBOT_MAX_STEPS` | `8` | Maximum tool-call rounds per request. |
| `JBOT_TIMEOUT` | `60` | LLM request timeout in seconds. |
| `JBOT_TEMPERATURE` | `0.2` | Model sampling temperature. |
| `JBOT_HISTORY_LIMIT` | `20` | Number of recent user/assistant messages retained. |

### Storage locations

```env
JBOT_MEMORY_FILE=./memory.json
JBOT_HISTORY_FILE=./history.json
JBOT_SESSIONS_DIR=./sessions
```

If omitted, these files are created under the configured sandbox directory.

### Optional web integrations

```env
NEWS_API_KEY=replace-with-news-api-key
TINYFISH_KEY=replace-with-tinyfish-key
PAXSENIX_API_KEY=replace-with-paxsenix-key
PAXSENIX_BASE_URL=https://api.paxsenix.org
```

Weather uses Open-Meteo. GitHub and Wikipedia use their public interfaces.
Some search paths require one of the optional search service credentials.

### Optional email configuration

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=replace-with-password
SMTP_FROM=your-email@example.com
```

Port `465` uses SMTP over SSL. Other ports use STARTTLS.

---

## Running J-Bot

### Primary interface

```bash
python -m jbot
```

The terminal interface includes:

- A header showing the application identity
- A scrollable conversation area
- Separate user and assistant message panels
- Live streamed responses
- Tool activity lines
- Plan and step status updates
- A command footer
- Keyboard cancellation

### Compatibility entry point

The repository also contains a backwards-compatible entry point:

```bash
python agent.py
```

The recommended entry point is still `python -m jbot`, because it uses the
current package layout directly.

---

## Terminal commands

Commands begin with `/` and are handled by the terminal interface before a
normal request is sent to the model.

| Command | Description |
|---|---|
| `/help` | Display the command reference. |
| `/tools` | List registered tool names. |
| `/search <query>` | Search immediately through the direct search action. |
| `/clear` | Clear the current persisted conversation history. |
| `/mem` | List stored durable memories. |
| `/memorize <key> <value>` | Store a durable fact. |
| `/recall <key>` | Retrieve a durable fact. |
| `/save <name>` | Save the current conversation as a named session. |
| `/load <name>` | Load a named session into the current history. |
| `/sessions` | List saved sessions. |
| `/plan <goal>` | Ask J-Bot to create and execute a multi-step plan. |
| `/exit` | Close the application. |
| `/quit` | Alias for `/exit`. |

### Keyboard controls

| Shortcut | Action |
|---|---|
| `Ctrl+C` | Cancel the active request, or exit when idle. |
| `Ctrl+Q` | Quit the application. |
| `Y` / `N` | Confirm or reject a deletion prompt. |

### Example session

```text
You: /memorize timezone Africa/Lagos
J-Bot: Memory saved.

You: What is the weather where I live?
J-Bot: [calls get_weather]
J-Bot: The current weather is ...

You: /save weekly-research
J-Bot: Session saved.
```

---

## Tool catalog

The following tools are currently registered by the project.

### File operations

| Tool | Purpose |
|---|---|
| `create_file` | Create or overwrite a text file. |
| `read_file` | Read a text file with a maximum read size. |
| `list_files` | List files and directories. |
| `copy_file` | Copy a file within the configured sandbox. |
| `move_file` | Move a file within the configured sandbox. |
| `remove_file` | Delete a file after explicit confirmation. |

### Shell and system

| Tool | Purpose |
|---|---|
| `run_shell` | Run a short command with a timeout and output limit. |
| `system_info` | Inspect platform, CPU, memory, and disk information. |

### Calculations and business utilities

| Tool | Purpose |
|---|---|
| `calculate` | Evaluate approved mathematical expressions. |
| `calculate_roi` | Calculate investment return and percentage return. |
| `read_spreadsheet` | Read spreadsheet data when the required reader is available. |
| `write_csv` | Write JSON rows to a CSV file. |
| `query_database` | Execute SQL against a local SQLite database. |
| `render_dynamic_page` | Fetch a page and extract readable text. |

### Research and public information

| Tool | Purpose |
|---|---|
| `web_search` | Search the web through configured search providers. |
| `web_fetch` | Fetch and simplify an HTTP or HTTPS page. |
| `get_weather` | Look up current weather through Open-Meteo. |
| `get_news` | Retrieve current news headlines. |
| `wikipedia_summary` | Retrieve a concise Wikipedia summary. |
| `translate_text` | Translate text through a remote translation endpoint. |
| `get_stock_price` | Retrieve stock information through `yfinance`. |

### GitHub

| Tool | Purpose |
|---|---|
| `github_user` | Inspect a GitHub user profile. |
| `github_users_repos` | List repositories for a GitHub user. |
| `github_search` | Search GitHub repositories, users, or code depending on the selected type. |
| `github_followers` | List follower information for a GitHub user. |

### Memory

| Tool | Purpose |
|---|---|
| `remember` | Store a durable key/value fact. |
| `recall` | Retrieve a durable fact by key. |
| `forget` | Remove a durable fact. |
| `list_memories` | List available durable memories. |

### Communication

| Tool | Purpose |
|---|---|
| `send_email` | Send email using configured SMTP credentials. |
| `send_notification` | Send an operating-system notification where supported. |
| `speak_text` | Read text aloud using an available speech backend. |

### Encrypted vault

| Tool | Purpose |
|---|---|
| `vault_set` | Encrypt and store a secret. |
| `vault_get` | Retrieve a stored secret. |
| `vault_list` | List secret identifiers without revealing values. |
| `vault_delete` | Delete a secret from the vault. |

The vault uses Fernet encryption and stores its generated key separately from
the encrypted data. Protect both the key file and the sessions directory.

### Learned skills and scheduled jobs

| Tool | Purpose |
|---|---|
| `skill_record` | Associate a user phrase with a tool and arguments. |
| `skill_suggest` | Suggest learned tools for a partial phrase. |
| `skill_forget` | Remove a learned phrase. |
| `schedule_job` | Store a recurring cron-like job. |
| `list_jobs` | List stored scheduled jobs. |
| `delete_job` | Delete a scheduled job by ID. |

Scheduled-job persistence exists in the current codebase, but a continuously
running executor is not yet connected to the main application loop. Treat
scheduled jobs as stored configuration until that integration is completed.

---

## Memory and persistence

J-Bot has two different types of context.

### Conversation history

Short-term dialogue is stored as a list of user and assistant messages. It is
trimmed to `JBOT_HISTORY_LIMIT`. Tool messages are used during a live turn but
are not included in the compact persisted follow-up history.

### Durable memory

Durable facts are stored as normalized keys and values:

```text
/memorize preferred_language Python
/recall preferred_language
```

The assistant can also call the memory tools directly when a request clearly
asks it to remember, recall, or forget something.

### Named sessions

Sessions are snapshots of the current history:

```text
/save client-research
/sessions
/load client-research
```

Session names are normalized to safe characters and limited in length.

---

## Multi-step planning

The `/plan` command uses a separate planning phase:

```text
/plan Prepare a market comparison for three competing products
```

J-Bot:

1. Asks the model to produce a short numbered plan.
2. Extracts the numbered steps.
3. Executes each step through the normal agent loop.
4. Carries the result of earlier steps into later steps.
5. Shows step progress in the terminal.
6. Returns the result of the final step.

The planning loop has its own maximum step count and can be cancelled with
`Ctrl+C`.

---

## Adding a custom tool

### 1. Create a tool function

Add a function to an imported module under `jbot/tools/`:

```python
from jbot.tools.registry import tool


@tool
def word_count(text: str):
    """
    Count the words in a text value.

    Args:
        text: Text to count.
    """
    return {"words": len(text.split())}
```

### 2. Import the module

Add the module to `jbot/tools/__init__.py` so the decorator runs during startup:

```python
from jbot.tools import business, calc, files, my_tool, search
```

The current package uses imports for registration. A module that is never
imported will not appear in `/tools` and will not be available to the model.

### 3. Keep the contract clear

Good tools should:

- Have a focused name.
- Include a complete docstring.
- Use typed parameters.
- Return a string or JSON-compatible value.
- Validate user-controlled input.
- Use bounded timeouts for network calls.
- Explain failures in a readable way.
- Avoid hiding destructive side effects.

### 4. Verify registration

Start J-Bot and run:

```text
/tools
```

The new function should appear in the registered tool list.

---

## Project structure

```text
J-bot/
├── jbot/
│   ├── __init__.py          Package metadata
│   ├── __main__.py         python -m jbot entry point
│   ├── agent.py            Agent loop and planning flow
│   ├── cli.py              CLI bridge to the TUI
│   ├── config.py           Environment and path configuration
│   ├── llm.py              OpenAI-compatible HTTP client
│   ├── session.py          Named session persistence
│   ├── tui.py              Primary Textual interface
│   ├── ui.py               Legacy Rich interface
│   └── tools/
│       ├── registry.py     Tool decorator, schemas, execution
│       ├── files.py        File operations
│       ├── shell.py        Shell execution
│       ├── calc.py         Safe expression calculations
│       ├── business.py     CSV, SQLite, email, and page utilities
│       ├── search.py       Search, weather, and page fetching
│       ├── github.py       GitHub tools
│       ├── memory.py       Durable memory
│       ├── skills.py       Vault, skills, and job storage
│       ├── notify.py       Notifications and speech
│       ├── news.py         News headlines
│       ├── stocks.py       Stock prices
│       ├── system.py       Machine information
│       ├── translate.py    Translation
│       └── wiki.py         Wikipedia
├── tests/
│   └── test_tools.py       Tool and persistence tests
├── agent.py                Backwards-compatible launcher
├── lfm.py                  Backwards-compatible API shim
├── jbot_ui.py              Legacy UI entry point
├── setup.py                Interactive setup wizard
├── requirements.txt        Python dependencies
├── .env.example            Configuration template
└── LICENSE                 MIT license
```

---

## Data and file locations

By default, J-Bot writes local state near the configured sandbox:

```text
memory.json              Durable memories
history.json             Recent conversation history
sessions/                Named sessions and job storage
sessions/vault.enc       Encrypted vault data
sessions/.vault_key      Vault encryption key
```

Add the following patterns to your personal or deployment-level ignore rules:

```gitignore
.env
history.json
memory.json
sessions/
```

Do not commit provider keys, SMTP passwords, vault keys, or conversation
history.

---

## Security boundaries

J-Bot can perform actions with real side effects. Treat it as a local
automation program, not as a hardened security sandbox.

### File operations

The file tools resolve paths against `JBOT_SANDBOX` and reject paths that
resolve outside that directory. Symlinks and permissions should still be
considered when choosing a sandbox location.

### Shell execution

`run_shell` executes commands from the sandbox working directory with a
timeout and a small blocklist. This is not process isolation or a container.
Do not point J-Bot at sensitive directories or give it access to an untrusted
prompt source without additional hardening.

### Network requests

Search, fetching, weather, news, GitHub, translation, stock, and email tools
may send data to external services. Review provider terms, credentials, and
the content being transmitted before using them with private information.

### Email and notifications

`send_email`, `send_notification`, and `speak_text` can create external or
local side effects. Configure only the integrations you intend to use.

### Credential handling

Use environment variables or the encrypted vault instead of putting secrets in
source files. Any credential that has appeared in a public repository should
be revoked and replaced.

---

## Troubleshooting

### No API key configured

Set the required provider variables in `.env`:

```env
USER_LLM_API_KEY=replace-with-your-key
USER_LLM_BASE_URL=https://api.example.com/v1
USER_LLM_MODEL=your-model
```

Restart the application after changing `.env`.

### Could not connect to the LLM API

Check:

1. The base URL includes the provider's API version path.
2. The model name is valid for that provider.
3. The endpoint is reachable from the machine.
4. The provider accepts OpenAI-style tool calls.
5. The configured timeout is long enough for the model.

### Feature-specific missing module

Some optional tools load their dependency only when called. Install the
missing package, then retry the feature. Common optional dependencies include
packages for cron parsing, desktop notifications, speech synthesis, and audio
playback.

### Textual interface does not start

Confirm the primary dependencies are installed:

```bash
python -m pip install -r requirements.txt
python -m jbot
```

If you are using a very small terminal window, resize it before starting the
full-screen interface.

### File tool rejects a path

The path must resolve inside `JBOT_SANDBOX`. Use a relative path such as:

```text
notes/research.txt
```

Do not use a path that escapes the sandbox with `..`.

### A delete request asks for confirmation

This is expected. Deletion is a two-stage operation:

1. J-Bot identifies the file and asks for confirmation.
2. The deletion proceeds only after an explicit confirmation.

---

## Testing

The project includes tests for:

- Calculator behavior
- File round trips
- Delete confirmation
- Shell blocklist behavior
- URL validation
- Session save/load
- Durable memory
- Tool schema registration

Run the test suite from the repository root:

```bash
python -m pytest tests -q
```

If `pytest` is not installed in your environment:

```bash
python -m pip install pytest
python -m pytest tests -q
```

For a dependency-free syntax check:

```bash
python -m compileall -q .
```

---

## Current implementation status

### Implemented

- Modular Python package layout
- Textual terminal interface
- OpenAI-compatible chat client
- Streaming responses
- Automatic tool schema generation
- Tool execution loop
- File and shell tools
- Durable memory
- Named sessions
- Encrypted vault
- Direct web and public-information tools
- Multi-step planning mode
- Cancellation support
- Compatibility launchers

### Under active consideration

- Stronger process isolation for shell commands
- Private-network blocking for URL fetchers
- Constraining SQLite paths to the sandbox
- Complete scheduler execution and notification loop
- More complete optional dependency declarations
- Broader test coverage for agent and provider behavior
- Provider-specific retry and rate-limit handling

The status section is intentionally explicit: a stored scheduled job is not
the same as a continuously running background scheduler, and a working
directory restriction is not the same as operating-system isolation.

---

## Contributing

Before adding a feature:

1. Identify whether it belongs in the agent, provider client, UI, or tools
   layer.
2. Keep tool inputs typed and documented.
3. Validate paths, URLs, credentials, and external side effects.
4. Add tests for normal behavior and failure behavior.
5. Update this README when a user-visible capability changes.
6. Keep secrets and generated runtime state out of version control.

### Contribution checklist

```text
[ ] The change has a focused responsibility.
[ ] User-controlled input is validated.
[ ] Network calls have bounded timeouts.
[ ] External side effects are obvious.
[ ] Errors are returned clearly.
[ ] Tests cover the important path.
[ ] Documentation matches the implementation.
[ ] No credentials or runtime state were committed.
```

---

## License

J-Bot is released under the MIT License. See [LICENSE](LICENSE) for the full
license text.

---

<div align="center">

Built for terminal workflows, local automation, and extensible AI tooling.

</div>