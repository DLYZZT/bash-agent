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

# Working directory (optional, defaults to ./work)
WORK_DIR=./work

# Confirm before execution (optional, defaults to yes)
CONFIRM_BEFORE_EXEC=yes
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

## Project Structure

```
bash-agent/
├── main.py              # Main program file
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
