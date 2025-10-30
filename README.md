# Bash Agent

Bash Agent 命令执行智能体。

## 功能特性

- 🤖 **智能命令执行**：基于 LLM 理解自然语言指令并生成相应的Shell命令
- 🔒 **安全防护**：内置多重安全机制，防止危险命令执行
- 📁 **隔离工作环境**：所有命令在指定的工作目录中执行，避免系统文件被误操作
- ⚡ **交互式体验**：支持 REPL 模式和单次命令执行
- 🛡️ **命令确认**：可配置执行前确认机制，防止意外操作
- 📊 **详细反馈**：提供命令执行结果、错误信息和退出码
- 🌐 **跨平台支持**：自动识别操作系统（macOS/Linux/Windows），根据平台执行相应的命令
- 🔌 **MCP 集成**：支持连接 Model Context Protocol (MCP) 服务器，扩展工具能力
- 💰 **Token 统计**：实时统计 API 调用次数、Token 消耗和预估成本
- 🗜️ **智能消息压缩**：自动检测上下文长度，超出限制时使用大模型总结压缩历史消息

## 安全机制

### 危险命令拦截
- 阻止经典自毁命令（如 `rm -rf /`）
- 拦截系统级危险操作（如 `sudo`、`mkfs`、`shutdown` 等）
- 防止访问系统敏感目录（如 `/etc`、`/root`）

### 路径隔离
- 限制命令执行在指定的工作目录内
- 阻止绝对路径访问
- 防止路径遍历攻击（`../` 等）

### 超时保护
- 默认 30 秒命令执行超时
- 可自定义超时时间
- 防止长时间运行的命令阻塞系统

## 安装与配置

### 环境要求
- Python 3.8+
- OpenAI API Key

### 安装依赖
```bash
pip install -r requirements.txt
```

### 环境配置
1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，配置以下变量：
```env
# OpenAI API 密钥（必需）
OPENAI_API_KEY=your_openai_api_key_here

# OpenAI 模型名称（可选，默认为 gpt-4o-mini）
OPENAI_MODEL=gpt-4o-mini

# 模型温度参数（可选，默认为 0.2）
MODEL_TEMPERATURE=0.2

# 工作目录（可选，默认为 ./work）
WORK_DIR=./work

# 执行前确认（可选，默认为 yes）
CONFIRM_BEFORE_EXEC=yes

# MCP 配置文件路径（可选，默认为 ./mcp_config.json）
MCP_CONFIG_PATH=./mcp_config.json

# 最大上下文 Token 数（可选，默认为 120000）
# 当消息超出此限制时，将自动压缩历史消息
MAX_CONTEXT_TOKENS=120000

# 保留最近的消息数（可选，默认为 10）
# 压缩时会保留最近的这么多条消息不被压缩
KEEP_RECENT_MESSAGES=10
```

## 使用方法

### 交互式模式
```bash
python main.py
```

启动后会进入交互式命令行界面：
```
Bash Agent. Type your goal or `exit` to quit.

You> 创建一个名为 test.txt 的文件，内容为 "Hello World"
```

### 单次命令模式
```bash
python main.py "列出当前目录下的所有文件"
```

### 示例用法

#### 查看帮助信息
```bash
You> /help
```

#### 文件操作
```bash
You> 创建一个名为 hello.py 的 Python 文件，内容包含一个简单的 hello world 函数
```

#### 查看 Token 统计
```bash
You> /stats
```

#### 清空对话历史
```bash
You> /clear
```

#### 手动压缩消息历史
```bash
You> /compress
```
即使未超出限制，也可以手动触发消息压缩，节省 Token 和成本。

## MCP 集成

Bash Agent 现在支持 Model Context Protocol (MCP)，可以同时连接多个 MCP 服务器并使用它们提供的工具。

### 什么是 MCP？

Model Context Protocol (MCP) 是一个开放协议，允许 AI 应用程序与外部工具和数据源进行标准化集成。通过 MCP，Bash Agent 可以：

- 同时连接多个 MCP 服务器
- 使用服务器提供的工具（如数据库查询、API 调用、文件操作等）
- 扩展 Agent 的能力，无需修改核心代码
- 使用 MCP 生态系统中的官方和社区服务器

### 配置 MCP 服务器

1. **创建配置文件**

   在项目根目录创建 `mcp_config.json` 文件：
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
       },
       "chrome-devtools": {
         "command": "npx",
         "args": [
           "-y",
           "@modelcontextprotocol/server-chrome-devtools"
         ]
       }
     },
     "enabled_servers": [
       "filesystem",
       "chrome-devtools"
     ]
   }
   ```

   **配置说明**：
   - 可以配置多个 MCP 服务器
   - 每个服务器需要指定 `command` 和 `args`
   - 支持 Node.js (`npx`) 和 Python (`python`) 服务器
   - 可选配置 `env` 环境变量
   - **可选 `enabled_servers` 数组**：如果提供，则只加载列表中的服务器。这样可以保留所有服务器配置，但选择性地启用/禁用它们，无需删除配置。如果省略或为 `null`，则加载 `mcpServers` 中的所有服务器。

2. **启动 Bash Agent**

   配置后启动 Bash Agent，它会自动连接到所有配置的 MCP 服务器：
   ```bash
   python main.py
   ```

   如果连接成功，你会看到：
   ```
   📡 正在连接 2 个 MCP 服务器...
   ✅ 已连接到 MCP 服务器 'filesystem'
      工具: ['read_file', 'write_file', 'list_directory']
   ✅ 已连接到 MCP 服务器 'sqlite'
      工具: ['query', 'execute']
   ✨ 成功连接 2/2 个 MCP 服务器
   ```

### MCP 架构

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

## 项目结构

```
bash-agent/
├── main.py                           # 程序入口
├── src/
│   ├── __init__.py
│   ├── agent.py                      # 主 Agent 类
│   ├── config.py                     # 环境与配置加载
│   ├── security.py                   # 命令安全校验
│   ├── message_manager.py            # 消息管理与压缩
│   ├── tool_handler.py               # 工具调用调度
│   ├── mcp_client.py                 # MCP 客户端集成
│   └── cli.py                        # 终端交互与提示
├── requirements.txt                  # Python 依赖
├── prompts/                          # 提示词目录
│   ├── system.md                     # 主系统提示词
│   └── summary.md                    # 消息总结提示词
├── work/                             # 工作目录（隔离环境）
└── README.md                         # 项目说明
```

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 免责声明

本工具仅用于合法的软件开发和运维任务。使用者需自行承担使用风险，开发者不对任何损失负责。请遵守相关法律法规和最佳实践。
