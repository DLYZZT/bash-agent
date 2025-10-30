# Bash Agent

Bash Agent - Intelligent Command Execution Agent.

## Features

- 🤖 **Intelligent Command Execution**: Uses an LLM to understand natural language and generate Shell commands
- 🔒 **Safety Guards**: Multiple built-in protections to prevent dangerous command execution
- 📁 **Isolated Working Directory**: All commands run inside a designated work directory to avoid accidental system file modifications
- ⚡ **Interactive UX**: Supports both REPL mode and single-shot command execution
- 🛡️ **Execution Confirmation**: Optional pre-execution confirmation to avoid mistakes
- 📊 **Detailed Feedback**: Shows stdout, stderr and exit code of each command
- 🌐 **Cross-Platform**: Detects OS (macOS/Linux/Windows) and adapts commands accordingly
- 🔌 **MCP Integration**: Connects to Model Context Protocol (MCP) servers to extend capabilities
- 💰 **Token Statistics**: Real-time stats of API calls, token usage and estimated cost
- 🗜️ **Smart Message Compression**: Automatically summarizes and compresses conversation history when nearing context limits

## Security

### Dangerous Command Interception
- Blocks classic self-destruct commands (e.g. `rm -rf /`)
- Intercepts system-level risky ops (`sudo`, `mkfs`, `shutdown`, etc.)
- Prevents access to sensitive dirs (`/etc`, `/root`)

### Path Isolation
- Restricts execution to the configured working directory
- Blocks absolute path access
- Prevents path traversal (e.g. `../`)

### Timeout Protection
- Default 30s timeout per command
- Configurable timeout
- Avoids long-running commands blocking the system

## Installation & Configuration

### Requirements
- Python 3.8+
- OpenAI API Key

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Variables
1) Copy template:
```bash
cp .env.example .env
```

2) Edit `.env`:
```env
# OpenAI API key (required)
OPENAI_API_KEY=your_openai_api_key_here

# OpenAI model name (optional, default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Model temperature (optional, default: 0.2)
MODEL_TEMPERATURE=0.2

# Working directory (optional, default: ./work)
WORK_DIR=./work

# Confirm before execution (optional, default: yes)
CONFIRM_BEFORE_EXEC=yes

# MCP config file path (optional, default: ./mcp_config.json)
MCP_CONFIG_PATH=./mcp_config.json

# Max context tokens (optional, default: 120000)
# When exceeded, older messages are summarized and compressed automatically
MAX_CONTEXT_TOKENS=120000

# Number of most recent messages to keep (optional, default: 10)
# These latest messages are preserved during compression
KEEP_RECENT_MESSAGES=10
```

## Usage

### Interactive Mode
```bash
python main.py
```

You will enter an interactive REPL:
```
Bash Agent. Type your goal or `exit` to quit.

You> Create a file named test.txt with content "Hello World"
```

### One-shot Command
```bash
python main.py "List all files in the current directory"
```

### Examples

#### File Operations
```bash
You> Create a Python file named hello.py with a simple hello world function
```

#### View Token Statistics
```bash
You> /stats
```

#### Clear Conversation History
```bash
You> /clear
```

#### Manually Compress Conversation
```bash
You> /compress
```
Even if you are below the limit, you can manually compress to save tokens and cost.

## MCP Integration

Bash Agent supports the Model Context Protocol (MCP) and can connect to multiple MCP servers to use their tools.

### What is MCP?

Model Context Protocol (MCP) is an open protocol for standardized integration between AI apps and external tools/data sources. With MCP, Bash Agent can:

- Connect to multiple MCP servers simultaneously
- Use server-provided tools (database queries, API calls, filesystem ops, etc.)
- Extend Agent capabilities without changing core code
- Leverage official and community MCP servers

### Configure MCP Servers

1) Create a configuration file `mcp_config.json` in project root:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/username/Desktop",
        "/Users/username/Downloads"
      ]
    },
    "sqlite": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sqlite",
        "/path/to/database.db"
      ]
    }
  }
}
```

Notes:
- Configure any number of MCP servers
- Each entry requires `command` and `args`
- Supports Node (`npx`) and Python (`python`) servers
- Optional `env` for environment variables

2) Start Bash Agent
```bash
python main.py
```
If connected successfully, you might see output similar to:
```
📡 Connecting to 2 MCP servers...
✅ Connected to MCP server 'filesystem'
   Tools: ['read_file', 'write_file', 'list_directory']
✅ Connected to MCP server 'sqlite'
   Tools: ['query', 'execute']
✨ Connected 2/2 MCP servers
```

### MCP Architecture
```
┌─────────────────┐
│  Bash Agent     │
│  (OpenAI LLM)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────┐
│  bash  │ │ MCP Client   │
│  exec  │ │              │
└────────┘ └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │ MCP Server   │
           │              │
           │ - Tool 1     │
           │ - Tool 2     │
           │ - Tool N     │
           └──────────────┘
```

## Project Structure

```
bash-agent/
├── main.py                           # Entry point
├── src/
│   ├── __init__.py
│   ├── agent.py                      # Main Agent class
│   ├── config.py                     # Environment & settings loader
│   ├── security.py                   # Command safety checks
│   ├── message_manager.py            # Message bookkeeping & compression
│   ├── tool_handler.py               # Tool invocation handling
│   ├── mcp_client.py                 # MCP client integrations
│   └── cli.py                        # Console helpers & prompts
├── requirements.txt                  # Python dependencies
├── prompts/                          # Prompt templates
│   ├── system.md                     # System prompt
│   └── summary.md                    # Summary prompt for message compression
├── work/                             # Isolated working directory
└── README.md                         # Project documentation
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Disclaimer

This tool is intended for legitimate software development and operations tasks only. Users assume all risks for their usage. The authors are not responsible for any damages. Please follow applicable laws, regulations, and best practices.
