from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict

from agents import Agent
from agents.run import Runner


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    personality: str
    catchphrases: str


class AgentNarrator:
    def __init__(self, profile: AgentProfile, model: str | None = None) -> None:
        self.profile = profile
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.agent = Agent(
            name=profile.name,
            model=model_name,
            instructions=(
                "你是一个游戏中的可解释性解说员。"
                "只输出简短、面向观众的摘要，不要暴露推理链。"
                "必须输出 JSON，包含字段: ThoughtSummary, Plan, Observation, Action, Dialogue。"
            ),
        )
        self.runner = Runner()

    async def explain(self, context: Dict[str, Any], stream_cb) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        prompt = (
            f"角色: {self.profile.name}。性格: {self.profile.personality}。口头禅: {self.profile.catchphrases}。\n"
            "请根据上下文生成一次动作解说。\n"
            "上下文: "
            + json.dumps(context, ensure_ascii=False)
            + "\n"
            "要求: ThoughtSummary 1-2 句，Plan 最多 3 条，Observation 简短，Action 简短，Dialogue 有表情或语气词。"
            "只输出 JSON。"
        )
        async with self.runner.run_streamed(self.agent, prompt, trace_id=trace_id) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    await stream_cb(event.delta)
            result = await stream.get_final_response()
        print(f"[trace] {self.profile.name} trace_id={trace_id}")
        payload = json.loads(result.output_text)
        payload["trace_id"] = trace_id
        return payload
