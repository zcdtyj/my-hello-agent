import os
import requests
# import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

SEARCH_ENDPOINT = "/coding_plan/search"

def get_current_date(query: str = "") -> str:
    """返回当前日期。query 参数保留是为了与 ToolExecutor 接口统一。"""
    print(f"📅 正在获取当前日期...")
    return datetime.now().strftime("%Y-%m-%d %A")

def search(query: str) -> str:
    print(f"🔍 正在执行 [MiniMax coding_plan] 网页搜索: {query}")
    try:
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")

        if not api_key or not base_url:
            return "错误:LLM_API_KEY 或 LLM_BASE_URL 未在 .env 文件中配置。"

        url = base_url.rstrip("/") + SEARCH_ENDPOINT
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(url, headers=headers, json={"q": query}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # print("DEBUG search raw response:", json.dumps(data, ensure_ascii=False, indent=2)[:1500])
        if data.get("base_resp", {}).get("status_code", 0) != 0:
            msg = data.get("base_resp", {}).get("status_msg", "未知错误")
            return f"搜索失败: {msg}"

        organic = data.get("organic") or []
        if not organic:
            return f"对不起，没有找到关于 '{query}' 的信息。"

        snippets = [
            f"[{i+1}] {res.get('title', '')}\n{res.get('snippet', '')}"
            for i, res in enumerate(organic[:3])
        ]
        return "\n\n".join(snippets)
    
    except requests.exceptions.RequestException as e:
        return f"搜索请求失败: {e}"
    except Exception as e:
        return f"搜索时发生错误: {e}"

class ToolExecutor:
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def registerTool(self, name: str, description: str, func: callable):
        if name in self.tools:
            print(f"警告:工具 '{name}' 已存在，将被覆盖。")
        self.tools[name] = {"description": description, "func": func}
        print(f"工具 '{name}' 已注册。")

    def getTool(self, name: str) -> callable:
        return self.tools.get(name, {}).get("func")

    def getAvailableTools(self) -> str:
        return "\n".join([
            f"- {name}: {info['description']}" 
            for name, info in self.tools.items()
        ])

if __name__ == '__main__':
    # 1. 初始化工具执行器
    toolExecutor = ToolExecutor()

    # 2. 注册我们的实战搜索工具
    search_description = "一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。"
    toolExecutor.registerTool("Search", search_description, search)
    
    # 3. 打印可用的工具
    print("\n--- 可用的工具 ---")
    print(toolExecutor.getAvailableTools())

    # 4. 智能体的Action调用，这次我们问一个实时性的问题
    print("\n--- 执行 Action: Search['英伟达最新的GPU型号是什么'] ---")
    tool_name = "Search"
    tool_input = "英伟达最新的GPU型号是什么"

    tool_function = toolExecutor.getTool(tool_name)
    if tool_function:
        observation = tool_function(tool_input)
        print("--- 观察 (Observation) ---")
        print(observation)
    else:
        print(f"错误:未找到名为 '{tool_name}' 的工具。")