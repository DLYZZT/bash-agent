# Bash Agent

Bash Agent 命令执行智能体。

## 功能特性

- 🤖 **智能命令执行**：基于 LLM 理解自然语言指令并生成相应的 Bash 命令
- 🔒 **安全防护**：内置多重安全机制，防止危险命令执行
- 📁 **隔离工作环境**：所有命令在指定的工作目录中执行，避免系统文件被误操作
- ⚡ **交互式体验**：支持 REPL 模式和单次命令执行
- 🛡️ **命令确认**：可配置执行前确认机制，防止意外操作
- 📊 **详细反馈**：提供命令执行结果、错误信息和退出码

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

# 工作目录（可选，默认为 ./work）
WORK_DIR=./work

# 执行前确认（可选，默认为 yes）
CONFIRM_BEFORE_EXEC=yes
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

#### 文件操作
```bash
You> 创建一个名为 hello.py 的 Python 文件，内容包含一个简单的 hello world 函数
```

## 项目结构

```
bash-agent/
├── main.py              # 主程序文件
├── requirements.txt     # Python 依赖
├── prompts/
│   └── system.md       # 系统提示词
├── work/               # 工作目录（隔离环境）
└── README.md           # 项目说明
```

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 免责声明

本工具仅用于合法的软件开发和运维任务。使用者需自行承担使用风险，开发者不对任何损失负责。请遵守相关法律法规和最佳实践。
