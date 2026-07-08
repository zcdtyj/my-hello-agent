import re
from llm_client import HelloAgentsLLM
from tools import ToolExecutor, search, get_current_date

# ReAct 提示词模板
REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可用工具如下:
{tools}

请严格按照以下格式进行回应:

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步行动。
- 首先判断问题是否涉及时间敏感信息（如"最新"、"最近"、"今年"、"现在"等）
- 如果涉及，先调用 DateTime 工具获取当前日期，再据此决定后续搜索的关键词
- 如果不涉及，直接基于问题字面意思规划行动
- 仔细阅读已有的观察结果，如果信息已经足够回答问题，立即用 Finish[...] 收尾
- 不要为了"更完整"而无限搜索细节
- 连续 2-3 次搜索都没有新信息时，应当 Finish
- 每次响应只能输出一个 Action，多个 Action 会被解析器丢弃

Action: 你决定采取的行动，必须是以下格式之一:
- `{{tool_name}}[{{tool_input}}]`:调用一个可用工具。
- `Finish[最终答案]`:当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在Action:字段后使用 Finish[最终答案] 来输出最终答案。

现在，请开始解决以下问题:
Question: {question}
History: {history}
"""

class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []

    def run(self, question: str):
        self.history = []
        current_step = 0
        retries_left = 2 

        while current_step < self.max_steps:
            current_step += 1
            print(f"--- 第 {current_step} 步 ---")

            tools_desc = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(tools=tools_desc, question=question, history=history_str)

            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)

            if not response_text:
                retries_left -= 1
                if retries_left > 0:
                    print(f"⚠️ 本次未能解析出有效Action，还剩 {retries_left} 次重试机会。")
                    # 往历史里塞一条提示，让 LLM 下次记得输出 Action
                    self.history.append({
                        "role": "user",
                        "content": "你刚才没有按格式输出 Action: Xxx[...]，请重新思考并严格按格式给出下一步行动。"
                    })
                    continue
                else:
                    print("⚠️ 多次重试仍未能解析Action，流程终止。")
                    break

            thought, action = self._parse_output(response_text)

            if thought:
                print(f"思考: {thought}")

            if not action:
                print("警告:未能解析出有效的Action，流程终止。")
                break

            if action.startswith("Finish"):
                final_answer_match = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
                if final_answer_match:
                    final_answer = final_answer_match.group(1)
                    print(f"🎉 最终答案: {final_answer}")
                    return final_answer
                else:
                    print(f"⚠️ Finish 格式无法解析: {action[:100]}")
                    break

            tool_name, tool_input = self._parse_action(action)
            if not tool_name:
                continue

            print(f"🎬 行动: {tool_name}[{tool_input}]")

            tool_function = self.tool_executor.getTool(tool_name)
            if not tool_function:
                observation = f"错误:未找到名为 '{tool_name}' 的工具。"
            else:
                observation = tool_function(tool_input)

            print(f"👀 观察: {observation}")

            self.history.append(f"Action: {action}")
            last_observations = [h for h in self.history if h.startswith("Observation:")]
            if len(last_observations) >= 2 and last_observations[-1] == last_observations[-2] == f"Observation: {observation}":
                print("⚠️ 检测到连续3次相同观察，终止循环防止死循环。")
                break
            self.history.append(f"Observation: {observation}")
        
        print("已达到最大步数，流程终止。")
        return None

    def _parse_output(self, text: str):
        normalized = text
        normalized = re.sub(r"(?m)^[ \t]*行动[::]", "Action:", normalized)
        normalized = re.sub(r"(?m)^[ \t]*思考[::]", "Thought:", normalized)

        thought_match = re.search(r"Thought:\s*(.*?)Action:", normalized, re.DOTALL)
        action_match = re.search(r"Action:(.*?)(?:Thought:|$)", normalized, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

             
    def _parse_action(self, action_text: str):
        match = re.match(r"(\w+)\[(.*)\]", action_text, re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        return None, None

if __name__ == '__main__':
    llm = HelloAgentsLLM()
    tool_executor = ToolExecutor()
    search_desc = "一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。"
    tool_executor.registerTool("Search", search_desc, search)
    datetime_desc = "返回当前的日期与星期。当问题涉及时间敏感信息（如'最新'、'最近'、'今天'等）时，应先调用此工具。"
    tool_executor.registerTool("DateTime", datetime_desc, get_current_date)
    agent = ReActAgent(llm_client = llm, tool_executor = tool_executor)
    question = "华为最新的手机是哪一款？它的主要卖点是什么？"
    agent.run(question)

    