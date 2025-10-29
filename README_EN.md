# Bash Agent

Bash Agent - Intelligent Command Execution Agent.

## Features

- 🤖 **Intelligent Command Execution**: Uses LLM to understand natural language instructions and generate corresponding Shell commands
- 🔒 **Security Protection**: Built-in multiple security mechanisms to prevent dangerous command execution
- 📁 **Isolated Work Environment**: All commands execute in a specified working directory to avoid accidental system file operations
- ⚡ **Interactive Experience**: Supports REPL mode and single command execution
- 🛡️ **Command Confirmation**: Configurable pre-execution confirmation mechanism to prevent accidental operations
- 📊 **Detailed Feedback**: Provides command execution results, error messages, and exit codes
- 🌐 **Cross-Platform Support**: Automatically detects the operating system (macOS/Linux/Windows) and executes appropriate commands for each platform
- 🔌 **MCP Integration**: Supports connecting to Model Context Protocol (MCP) servers to extend tool capabilities
- 💰 **Token Statistics**: Real-time tracking of API calls, token consumption, and estimated costs

## Security Mechanisms

### Dangerous Command Interception
- Blocks classic self-destruct commands (such as `rm -rf /`)
- Intercepts system-level dangerous operations (such as `sudo`, `mkfs`, `shutdown`, etc.)
- Prevents access to system sensitive directories (such as `/etc`, `/root`)

### Path Isolation
- Restricts command execution within the specified working directory
- Blocks absolute path access
- Prevents path traversal attacks (`../` etc.)

### Timeout Protection
- Default 30-second command execution timeout
- Customizable timeout duration
- Prevents long-running commands from blocking the system

## Installation and Configuration

### Requirements
- Python 3.8+
- OpenAI API Key

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Configuration
1. Copy the environment variable template:
```bash
cp .env.example .env
```

2. Edit the `.env` file and configure the following variables:
```env
# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key_here

# OpenAI model name (optional, defaults to gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Model temperature parameter (optional, defaults to 0.2)
MODEL_TEMPERATURE=0.2

# Working directory (optional, defaults to ./work)
WORK_DIR=./work

# Confirm before execution (optional, defaults to yes)
CONFIRM_BEFORE_EXEC=yes

# MCP configuration file path (optional, defaults to ./mcp_config.json)
MCP_CONFIG_PATH=./mcp_config.json
```

## Usage

### Interactive Mode
```bash
python main.py
```

After startup, you'll enter the interactive command line interface:
```
Bash Agent. Type your goal or `exit` to quit.

You> Create a file named test.txt with content "Hello World"
```

### Single Command Mode
```bash
python main.py "List all files in the current directory"
```

### Example Usage

#### File Operations
```bash
You> Create a Python file named hello.py with content containing a simple hello world function
```

#### View Token Statistics
```bash
You> /stats
```

## MCP Integration

Bash Agent now supports the Model Context Protocol (MCP), allowing it to connect to multiple MCP servers simultaneously and use their provided tools.

### What is MCP?

Model Context Protocol (MCP) is an open protocol that allows AI applications to integrate with external tools and data sources in a standardized way. Through MCP, Bash Agent can:

- Connect to multiple MCP servers simultaneously
- Use tools provided by servers (such as database queries, API calls, file operations, etc.)
- Extend the Agent's capabilities without modifying the core code
- Utilize official and community servers from the MCP ecosystem

### Configuring MCP Servers

1. **Create Configuration File**

   Create a `mcp_config.json` file in the project root directory:
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

   **Configuration notes**:
   - You can configure multiple MCP servers
   - Each server requires `command` and `args`
   - Supports Node.js (`npx`) and Python (`python`) servers
   - Optional `env` environment variables

2. **Start Bash Agent**

   After configuration, start Bash Agent and it will automatically connect to all configured MCP servers:
   ```bash
   python main.py
   ```

   If connection is successful, you will see:
   ```
   📡 正在连接 2 个 MCP 服务器...
   ✅ 已连接到 MCP 服务器 'filesystem'
      工具: ['read_file', 'write_file', 'list_directory']
   ✅ 已连接到 MCP 服务器 'sqlite'
      工具: ['query', 'execute']
   ✨ 成功连接 2/2 个 MCP 服务器
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
├── main.py              # Main program file
├── mcp_client.py        # MCP client module
├── requirements.txt     # Python dependencies
├── prompts/
│   └── system.md       # System prompt
├── work/               # Working directory (isolated environment)
└── README.md           # Project documentation
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Disclaimer

This tool is intended for legitimate software development and operations tasks only. Users are responsible for their own usage risks, and developers are not liable for any losses. Please comply with relevant laws, regulations, and best practices.
