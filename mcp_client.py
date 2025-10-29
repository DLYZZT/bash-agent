import os
import asyncio
import json
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPServerConnection:
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化 MCP 服务器连接
        
        Args:
            name: 服务器名称
            config: 服务器配置，包含 command 和 args
        """
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        
    async def connect(self, exit_stack: AsyncExitStack) -> bool:
        """
        连接到 MCP 服务器
        
        Args:
            exit_stack: 异步退出栈，用于资源管理
            
        Returns:
            bool: 连接是否成功
        """
        try:
            command = self.config.get("command")
            args = self.config.get("args", [])
            env = self.config.get("env")
            
            if not command:
                print(f"❌ 服务器 '{self.name}' 缺少 command 配置")
                return False
            
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env
            )
            
            # 建立连接
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            self.session = await exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            
            # 初始化会话
            await self.session.initialize()
            
            # 获取可用工具列表
            response = await self.session.list_tools()
            self.available_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                for tool in response.tools
            ]
            
            print(f"✅ 已连接到 MCP 服务器 '{self.name}'")
            # print(f"   工具: {[tool['name'] for tool in self.available_tools]}")
            
            return True
            
        except Exception as e:
            print(f"❌ 连接 MCP 服务器 '{self.name}' 失败: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果
        """
        if not self.session:
            return {
                "success": False,
                "error": f"服务器 '{self.name}' 未连接"
            }
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            content_list = []
            for item in result.content:
                if hasattr(item, 'text'):
                    content_list.append({
                        "type": "text",
                        "text": item.text
                    })
                elif hasattr(item, 'data'):
                    content_list.append({
                        "type": getattr(item, 'type', 'unknown'),
                        "data": str(item.data) if hasattr(item, 'data') else str(item)
                    })
                else:
                    content_list.append({
                        "type": "text",
                        "text": str(item)
                    })
            
            return {
                "success": True,
                "content": content_list,
                "is_error": result.isError if hasattr(result, 'isError') else False
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """
        将 MCP 工具转换为 OpenAI 函数调用格式
        
        Returns:
            List[Dict]: OpenAI 格式的工具列表
        """
        openai_tools = []
        for tool in self.available_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": f"mcp_{self.name}_{tool['name']}",
                    "description": f"[{self.name}] {tool['description']}",
                    "parameters": tool['input_schema']
                }
            })
        return openai_tools
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.session is not None


class MCPClient:
    """MCP 客户端，支持多个服务器连接"""
    
    def __init__(self):
        """初始化 MCP 客户端"""
        self.servers: Dict[str, MCPServerConnection] = {}
        self.exit_stack = AsyncExitStack()
        
    async def connect_from_config(self, config: Dict[str, Any]) -> int:
        """
        从配置字典连接到所有 MCP 服务器
        
        Args:
            config: MCP 配置字典，格式为 {"mcpServers": {...}}
            
        Returns:
            int: 成功连接的服务器数量
        """
        mcp_servers = config.get("mcpServers", {})
        
        if not mcp_servers:
            print("⚠️  配置中没有 MCP 服务器")
            return 0
        
        print(f"📡 正在连接 {len(mcp_servers)} 个 MCP 服务器...")
        
        success_count = 0
        for name, server_config in mcp_servers.items():
            server = MCPServerConnection(name, server_config)
            if await server.connect(self.exit_stack):
                self.servers[name] = server
                success_count += 1
        
        if success_count > 0:
            print(f"✨ 成功连接 {success_count}/{len(mcp_servers)} 个 MCP 服务器")
        else:
            print("⚠️  没有成功连接任何 MCP 服务器")
        
        return success_count
    
    async def call_tool(self, full_tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 MCP 工具
        
        Args:
            full_tool_name: 完整工具名称，格式为 "mcp_<server_name>_<tool_name>"
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果
        """

        if not full_tool_name.startswith("mcp_"):
            return {
                "success": False,
                "error": "工具名称格式错误"
            }
        
        parts = full_tool_name[4:].split("_", 1)
        if len(parts) != 2:
            return {
                "success": False,
                "error": f"无法解析工具名称: {full_tool_name}"
            }
        
        server_name, tool_name = parts
        
        server = self.servers.get(server_name)
        if not server:
            return {
                "success": False,
                "error": f"服务器 '{server_name}' 未连接"
            }
        
        return await server.call_tool(tool_name, arguments)
    
    def get_all_tools_for_openai(self) -> List[Dict[str, Any]]:
        """
        获取所有服务器的工具，转换为 OpenAI 格式
        
        Returns:
            List[Dict]: OpenAI 格式的工具列表
        """
        all_tools = []
        for server in self.servers.values():
            all_tools.extend(server.get_tools_for_openai())
        return all_tools
    
    async def cleanup(self):
        """清理资源"""
        try:

            for server in self.servers.values():
                if server.session:
                    try:
                        pass
                    except Exception:
                        pass
            await self.exit_stack.aclose()
        except Exception as e:
            pass
    
    def is_connected(self) -> bool:
        """检查是否有任何服务器已连接"""
        return len(self.servers) > 0
    
    def get_servers_info(self) -> Dict[str, Any]:
        """获取所有服务器的信息"""
        return {
            name: {
                "connected": server.is_connected(),
                "tools": [t["name"] for t in server.available_tools]
            }
            for name, server in self.servers.items()
        }


class MCPClientManager:
    """MCP 客户端管理器，支持异步操作的同步封装"""
    
    def __init__(self):
        self.client = MCPClient()
        self.loop = None
        self._is_running = False
        
    def connect_from_config_file(self, config_path: str) -> bool:
        """
        从配置文件连接到 MCP 服务器
        
        Args:
            config_path: 配置文件路径（JSON 格式）
            
        Returns:
            bool: 是否成功连接至少一个服务器
        """
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                print(f"❌ 配置文件不存在: {config_path}")
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            success_count = self.loop.run_until_complete(
                self.client.connect_from_config(config)
            )
            
            if success_count > 0:
                self._is_running = True
                return True
            
            return False
            
        except json.JSONDecodeError as e:
            print(f"❌ 配置文件格式错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def connect_from_config_dict(self, config: Dict[str, Any]) -> bool:
        """
        从配置字典连接到 MCP 服务器
        
        Args:
            config: MCP 配置字典
            
        Returns:
            bool: 是否成功连接至少一个服务器
        """
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            success_count = self.loop.run_until_complete(
                self.client.connect_from_config(config)
            )
            
            if success_count > 0:
                self._is_running = True
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步方式调用 MCP 工具
        
        Args:
            tool_name: 完整工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果
        """
        if not self._is_running:
            return {
                "success": False,
                "error": "MCP 客户端未运行"
            }
        
        try:
            result = self.loop.run_until_complete(
                self.client.call_tool(tool_name, arguments)
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """获取 OpenAI 格式的工具列表"""
        return self.client.get_all_tools_for_openai()
    
    def get_servers_info(self) -> Dict[str, Any]:
        """获取所有服务器的信息"""
        return self.client.get_servers_info()
    
    def cleanup(self):
        """清理资源"""
        if self._is_running and self.loop:
            try:
                if not self.loop.is_closed():
                    try:
                        self.loop.run_until_complete(self.client.cleanup())
                    except Exception:
                        pass
                    try:
                        self.loop.close()
                    except Exception:
                        pass
                
                self._is_running = False
            except Exception:
                self._is_running = False
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_running and self.client.is_connected()
