from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional

from .agents import AgentNarrator, AgentProfile
from .world import EventBus, World

ActionCallable = Callable[[], Awaitable[None]]


@dataclass
class Mission:
    mission_id: str
    title: str
    description: str
    actions: List[ActionCallable]


class ExecutionController:
    def __init__(self) -> None:
        self.paused = False
        self.step_requested = False
        self._event = asyncio.Event()
        self._event.set()

    async def wait(self) -> None:
        # Gate each action for pause/step controls.
        while self.paused and not self.step_requested:
            await self._event.wait()
            self._event.clear()
        if self.step_requested:
            self.step_requested = False
            self.paused = True

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._event.set()

    def step(self) -> None:
        self.step_requested = True
        self._event.set()


class MissionRunner:
    def __init__(self, world: World, bus: EventBus) -> None:
        self.world = world
        self.bus = bus
        self.controller = ExecutionController()
        self.current_task: Optional[asyncio.Task] = None
        self.lan = AgentNarrator(
            AgentProfile(
                "lan",
                "阿岚",
                "冷静理性、策略控、说话短、会做风险检查。",
                "我先把路径和代价算清楚。别急，先确认条件。",
            )
        )
        self.xia = AgentNarrator(
            AgentProfile(
                "xia",
                "小夏",
                "乐观行动派、爱吐槽、社交高手、边走边观察彩蛋。",
                "OK！我上！这 NPC 绝对藏话。我去问路～",
            )
        )
        self.missions = self._build_missions()

    def get_mission(self, mission_id: str) -> Mission:
        return self.missions[mission_id]

    async def run_mission(self, mission: Mission) -> None:
        await self.bus.emit({"type": "task_status", "payload": {"status": "start", "title": mission.title}})
        for action in mission.actions:
            await self.controller.wait()
            await action()
        await self.bus.emit({"type": "task_status", "payload": {"status": "complete", "title": mission.title}})

    def start(self, mission_id: str) -> None:
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        mission = self.get_mission(mission_id)
        self.current_task = asyncio.create_task(self.run_mission(mission))

    def pause(self) -> None:
        self.controller.pause()

    def resume(self) -> None:
        self.controller.resume()

    def step(self) -> None:
        self.controller.step()

    def _build_missions(self) -> Dict[str, Mission]:
        return {
            "task_a": Mission(
                "task_a",
                "新手任务：买苹果送回家",
                "去商店买 2 个苹果，然后送到家门口。",
                [
                    self._lan_go_shop,
                    self._xia_go_shop,
                    self._lan_pick_apples,
                    self._xia_pick_apples,
                    self._lan_go_home,
                    self._xia_go_home,
                    self._deliver_apples,
                ],
            ),
            "task_b": Mission(
                "task_b",
                "协作机关：双人开关门",
                "两人分头取线索 -> 汇合到双人开关门 -> 拿到钥匙 -> 交给守门 NPC。",
                [
                    self._xia_ask_villager,
                    self._lan_check_guard,
                    self._both_to_switches,
                    self._both_open_door,
                    self._lan_get_key,
                    self._both_to_guard,
                    self._both_talk_guard,
                ],
            ),
            "task_c": Mission(
                "task_c",
                "轻喜剧任务：找走失的小猫",
                "跟着脚印找猫咪，过程互相吐槽，最终配合完成。",
                [
                    self._xia_ask_villager,
                    self._lan_scan_trail,
                    self._both_find_cat,
                    self._both_return_home,
                ],
            ),
        }

    async def _emit_agent_event(self, agent_id: str, payload: dict) -> None:
        await self.bus.emit({"type": "agent_event", "payload": {"agent_id": agent_id, **payload}})

    async def _emit_stream(self, agent_id: str, text: str) -> None:
        await self.bus.emit({"type": "agent_stream", "payload": {"agent_id": agent_id, "text": text}})

    async def _explain(self, agent_id: str, context: dict) -> None:
        narrator = self.lan if agent_id == "lan" else self.xia
        result = await narrator.explain(context, lambda chunk: self._emit_stream(agent_id, chunk))
        await self._emit_agent_event(agent_id, result)
        await self.bus.emit({"type": "trace", "payload": {"agent_id": agent_id, "trace_id": result["trace_id"]}})

    async def _move_agent(self, agent_id: str, target: tuple[int, int], action_label: str) -> None:
        agent = self.world.get_agent(agent_id)
        start = agent.pos
        path = self.world.find_path(agent.pos, target)
        for step in path:
            await self.controller.wait()
            await self.world.move_agent(agent_id, step)
            await asyncio.sleep(0.2)
        await self._explain(
            agent_id,
            {
                "action": action_label,
                "from": start,
                "to": target,
                "observation": self.world.nearby(agent_id),
            },
        )

    async def _lan_go_shop(self) -> None:
        await self._move_agent("lan", (3, 2), "前往商店")

    async def _xia_go_shop(self) -> None:
        await self._move_agent("xia", (4, 2), "前往商店")

    async def _lan_pick_apples(self) -> None:
        await self._move_agent("lan", (4, 2), "挑选苹果")
        await self.world.pickup("lan", "apple1")
        await self._explain(
            "lan",
            {
                "action": "拾取苹果",
                "observation": "确认苹果在货架上",
                "inventory": self.world.get_agent("lan").inventory,
            },
        )

    async def _xia_pick_apples(self) -> None:
        await self._move_agent("xia", (5, 2), "挑选苹果")
        await self.world.pickup("xia", "apple2")
        await self._explain(
            "xia",
            {
                "action": "拾取苹果",
                "observation": "老板点头示意",
                "inventory": self.world.get_agent("xia").inventory,
            },
        )

    async def _lan_go_home(self) -> None:
        await self._move_agent("lan", (18, 1), "前往家门口")

    async def _xia_go_home(self) -> None:
        await self._move_agent("xia", (18, 2), "前往家门口")

    async def _deliver_apples(self) -> None:
        await self.world.drop("lan", "apple1", (18, 1))
        await self.world.drop("xia", "apple2", (18, 2))
        await self._explain(
            "xia",
            {"action": "放下苹果", "observation": "家门口已收到"},
        )
        await self._explain(
            "lan",
            {"action": "确认交付", "observation": "任务完成"},
        )

    async def _xia_ask_villager(self) -> None:
        await self._move_agent("xia", (12, 4), "询问路人")
        reply = await self.world.talk("xia", "villager", "今天有什么线索吗？")
        await self._explain(
            "xia",
            {"action": "对话", "observation": reply, "dialogue_hint": "NPC 情报"},
        )

    async def _lan_check_guard(self) -> None:
        await self._move_agent("lan", (16, 10), "查看守门人")
        reply = await self.world.talk("lan", "guard", "我们需要什么条件？")
        await self._explain(
            "lan",
            {"action": "对话", "observation": reply, "dialogue_hint": "需要两人"},
        )

    async def _both_to_switches(self) -> None:
        await self._move_agent("lan", (10, 10), "站上开关 A")
        await self._move_agent("xia", (12, 10), "站上开关 B")
        await self._explain(
            "lan",
            {"action": "协作站位", "observation": "双人开关准备就绪"},
        )

    async def _both_open_door(self) -> None:
        await self.world.update_door_state()
        await self._explain(
            "xia",
            {"action": "触发机关", "observation": "双人门开启"},
        )

    async def _lan_get_key(self) -> None:
        await self._move_agent("lan", (15, 10), "进入门后取钥匙")
        await self.world.pickup("lan", "key")
        await self._explain(
            "lan",
            {"action": "拾取钥匙", "observation": "钥匙入手"},
        )

    async def _both_to_guard(self) -> None:
        await self._move_agent("lan", (16, 10), "返回守门人")
        await self._move_agent("xia", (16, 10), "回到守门人")

    async def _both_talk_guard(self) -> None:
        reply = await self.world.talk("lan", "guard", "钥匙已拿到。")
        await self._explain(
            "lan",
            {"action": "交付钥匙", "observation": reply},
        )
        await self._explain(
            "xia",
            {"action": "补充说明", "observation": "守门人放行"},
        )

    async def _lan_scan_trail(self) -> None:
        await self._move_agent("lan", (14, 3), "分析脚印")
        await self._explain(
            "lan",
            {"action": "观察脚印", "observation": "脚印延伸向东"},
        )

    async def _both_find_cat(self) -> None:
        await self._move_agent("xia", (17, 3), "寻找小猫")
        await self._move_agent("lan", (17, 3), "支援小夏")
        await self.world.pickup("xia", "cat")
        await self._explain(
            "xia",
            {"action": "找到小猫", "observation": "猫咪喵喵回应"},
        )

    async def _both_return_home(self) -> None:
        await self._move_agent("xia", (18, 2), "带猫回家")
        await self._move_agent("lan", (18, 1), "确认归还")
        await self._explain(
            "lan",
            {"action": "任务收尾", "observation": "猫咪安全"},
        )
