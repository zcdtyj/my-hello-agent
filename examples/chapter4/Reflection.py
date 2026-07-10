from typing import List, Dict, Any
from llm_client import HelloAgentsLLM

SYSTEM_INITIAL = "你是一位资深的Python程序员。请编写满足PEP 8规范的Python函数，包含完整的函数签名和文档字符串。"
SYSTEM_REFLECT = "你是一位极其严格的代码评审专家和资深算法工程师，对代码的性能有极致的要求。专注找出算法效率上的主要瓶颈，提出具体可行的改进建议。如果代码在算法层面已经最优，只回答'无需改进'。"
SYSTEM_REFINE = "你是一位资深的Python程序员。你正在根据一位代码评审专家的反馈来优化你的代码。"

class Memory:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def add_record(self, record_type: str, content: str):
        record = {"type": record_type, "content": content}
        self.records.append(record)
        print(f"📝 记忆已更新，新增一条 '{record_type}' 记录。")

    def get_trajectory(self) -> str:
        trajectory_parts = []
        for record in self.records:
            if record['type'] == 'execution':
                trajectory_parts.append(f"--- 上一轮尝试 (代码) ---\n{record['content']}")
            elif record['type'] == 'reflection':
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")

        return "\n\n".join(trajectory_parts)

    def get_last_execution(self) -> str:
        for record in reversed(self.records):
            if record['type'] == 'execution':
                return record['content']
        return None


INITIAL_PROMPT_TEMPLATE = """
要求: {task}

请直接输出代码，不要包含任何额外的解释。
"""

REFLECT_PROMPT_TEMPLATE = """
# 原始任务:
{task}

# 待审查的代码:
```python
{code}
```

请分析该代码的时间复杂度，并思考是否存在一种<strong>算法上更优</strong>的解决方案来显著提升性能。
如果存在，请清晰地指出当前算法的不足，并提出具体的、可行的改进算法建议（例如，使用筛法替代试除法）。
如果代码在算法层面已经达到最优，才能回答“无需改进”。

请直接输出你的反馈，不要包含任何额外的解释。
"""


REFINE_PROMPT_TEMPLATE = """
# 原始任务:
{task}

# 你上一轮尝试的代码:
{last_code_attempt}
评审员的反馈：
{feedback}

请根据评审员的反馈，生成一个优化后的新版本代码。
请直接输出优化后的代码，不要包含任何额外的解释。
"""

class ReflectionAgent:
    def __init__(self, llm_client, max_iterations=3):
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_iterations = max_iterations

    def run(self, task: str):
        print(f"\n--- 开始处理任务 ---\n任务: {task}")

        print("\n--- 正在进行初始尝试 ---")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt, system=SYSTEM_INITIAL)
        self.memory.add_record('execution', initial_code)

        for i in range(self.max_iterations):
            print(f"\n--- 第 {i+1}/{self.max_iterations} 轮迭代 ---")

            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution()
            reflect_prompt = REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflect_prompt, system=SYSTEM_REFLECT)
            self.memory.add_record("reflection", feedback)

            if "无需改进" in feedback:
                print("\n✅ 反思认为代码已无需改进，任务完成。")
                break

            print("\n-> 正在进行优化...")
            refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task,
                last_code_attempt=last_code,
                feedback=feedback
            )
            refine_code = self._get_llm_response(refine_prompt, system=SYSTEM_REFINE)
            self.memory.add_record("execution", refine_code)

        final_code = self.memory.get_last_execution()
        print(f"\n--- 任务完成 ---\n最终生成的代码:\n```python\n{final_code}\n```")
        return final_code

    def _get_llm_response(self, prompt: str, system: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        response_text = self.llm_client.think(messages=messages) or ""
        return response_text

if __name__ == '__main__':
    try:
        llm_client = HelloAgentsLLM()
    except Exception as e:
        print(f"初始化LLM客户端时出错: {e}")
        exit()

    agent = ReflectionAgent(llm_client, max_iterations=2)

    task = "编写一个Python函数，找出1到n之间所有的素数 (prime numbers)。"
    agent.run(task)
            
