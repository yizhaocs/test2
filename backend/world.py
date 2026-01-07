from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

GridPos = Tuple[int, int]


@dataclass
class Tile:
    kind: str
    walkable: bool


@dataclass
class Item:
    item_id: str
    name: str
    pos: GridPos
    held_by: Optional[str] = None


@dataclass
class NPC:
    npc_id: str
    name: str
    pos: GridPos
    dialog: List[str]
    requires_both: bool = False
    gives_item: Optional[str] = None


@dataclass
class Switch:
    switch_id: str
    pos: GridPos
    engaged_by: Optional[str] = None


@dataclass
class Door:
    door_id: str
    pos: GridPos
    open: bool = False


@dataclass
class AgentState:
    agent_id: str
    name: str
    pos: GridPos
    inventory: List[str] = field(default_factory=list)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def emit(self, event: dict) -> None:
        for queue in list(self._subscribers):
            await queue.put(event)


class World:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.width = 20
        self.height = 14
        self.grid = self._build_grid()
        self.agents: Dict[str, AgentState] = {
            "lan": AgentState("lan", "阿岚", (2, 2)),
            "xia": AgentState("xia", "小夏", (3, 2)),
        }
        self.items: Dict[str, Item] = {
            "apple1": Item("apple1", "苹果", (4, 2)),
            "apple2": Item("apple2", "苹果", (5, 2)),
            "key": Item("key", "钥匙", (15, 10)),
            "cat": Item("cat", "走失的小猫", (17, 3)),
        }
        self.npcs: Dict[str, NPC] = {
            "shopkeeper": NPC(
                "shopkeeper",
                "店主",
                (3, 2),
                ["欢迎光临！", "苹果今天很甜哦。"],
            ),
            "guard": NPC(
                "guard",
                "守门人",
                (16, 10),
                ["需要钥匙才能通过。", "你们两位一起说我才放心。"],
                requires_both=True,
            ),
            "villager": NPC(
                "villager",
                "路人",
                (12, 4),
                ["天气？今天晴。", "你们在找猫？我看到脚印往东。"],
            ),
        }
        self.switches: Dict[str, Switch] = {
            "switch_a": Switch("switch_a", (10, 10)),
            "switch_b": Switch("switch_b", (12, 10)),
        }
        self.doors: Dict[str, Door] = {
            "dual_door": Door("dual_door", (14, 10)),
        }
        self.synergy = 0

    def _build_grid(self) -> List[List[Tile]]:
        layout = [
            "####################",
            "#......~~~~......#H#",
            "#..S...~~~~..####..#",
            "#......~~~~..#..#..#",
            "#......~~~~..#..#..#",
            "#..####......#..#..#",
            "#..#..#......#..#..#",
            "#..#..#..######..#.#",
            "#..#..#............#",
            "#..#..#####.#####..#",
            "#..#......A.B.D....#",
            "#..#...............#",
            "#..#...............#",
            "####################",
        ]
        grid: List[List[Tile]] = []
        for y, row in enumerate(layout):
            grid_row: List[Tile] = []
            for x, char in enumerate(row):
                if char == "#":
                    grid_row.append(Tile("wall", False))
                elif char == "~":
                    grid_row.append(Tile("water", False))
                elif char == "S":
                    grid_row.append(Tile("shop", True))
                elif char == "H":
                    grid_row.append(Tile("home", True))
                elif char in {"A", "B"}:
                    grid_row.append(Tile("switch", True))
                elif char == "D":
                    grid_row.append(Tile("door", True))
                else:
                    grid_row.append(Tile("grass", True))
            grid.append(grid_row)
        return grid

    def in_bounds(self, pos: GridPos) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, pos: GridPos) -> bool:
        if not self.in_bounds(pos):
            return False
        tile = self.grid[pos[1]][pos[0]]
        if tile.kind == "door":
            door = self.doors["dual_door"]
            return door.open
        return tile.walkable

    def tile_kind(self, pos: GridPos) -> str:
        return self.grid[pos[1]][pos[0]].kind

    def get_agent(self, agent_id: str) -> AgentState:
        return self.agents[agent_id]

    def neighbors(self, pos: GridPos) -> List[GridPos]:
        x, y = pos
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [p for p in candidates if self.is_walkable(p)]

    def heuristic(self, a: GridPos, b: GridPos) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start: GridPos, goal: GridPos) -> List[GridPos]:
        # A* pathfinding on grid for walkable tiles.
        if start == goal:
            return []
        frontier: List[Tuple[float, GridPos]] = [(0, start)]
        came_from: Dict[GridPos, Optional[GridPos]] = {start: None}
        cost_so_far: Dict[GridPos, float] = {start: 0}
        while frontier:
            frontier.sort(key=lambda x: x[0])
            _, current = frontier.pop(0)
            if current == goal:
                break
            for nxt in self.neighbors(current):
                new_cost = cost_so_far[current] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self.heuristic(goal, nxt)
                    frontier.append((priority, nxt))
                    came_from[nxt] = current
        if goal not in came_from:
            return []
        path: List[GridPos] = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    async def emit_world(self) -> None:
        await self.bus.emit(
            {
                "type": "world_update",
                "payload": self.serialize(),
            }
        )

    def serialize(self) -> dict:
        tile_kinds = {}
        for y, row in enumerate(self.grid):
            for x, tile in enumerate(row):
                tile_kinds[f"{x},{y}"] = tile.kind
        return {
            "width": self.width,
            "height": self.height,
            "tileKinds": tile_kinds,
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "x": agent.pos[0],
                    "y": agent.pos[1],
                    "inventory": list(agent.inventory),
                }
                for agent_id, agent in self.agents.items()
            },
            "items": {
                item_id: {
                    "name": item.name,
                    "x": item.pos[0],
                    "y": item.pos[1],
                    "held_by": item.held_by,
                }
                for item_id, item in self.items.items()
                if item.held_by is None
            },
            "switches": {
                switch_id: {
                    "x": sw.pos[0],
                    "y": sw.pos[1],
                    "engaged_by": sw.engaged_by,
                }
                for switch_id, sw in self.switches.items()
            },
            "doors": {
                door_id: {
                    "x": door.pos[0],
                    "y": door.pos[1],
                    "open": door.open,
                }
                for door_id, door in self.doors.items()
            },
            "npcs": {
                npc_id: {
                    "name": npc.name,
                    "x": npc.pos[0],
                    "y": npc.pos[1],
                    "requires_both": npc.requires_both,
                }
                for npc_id, npc in self.npcs.items()
            },
            "synergy": self.synergy,
        }

    async def move_agent(self, agent_id: str, pos: GridPos) -> None:
        agent = self.agents[agent_id]
        agent.pos = pos
        for sw in self.switches.values():
            if agent.pos == sw.pos:
                sw.engaged_by = agent_id
            elif sw.engaged_by == agent_id:
                sw.engaged_by = None
        await self.update_door_state()
        await self.emit_world()

    async def update_door_state(self) -> None:
        door = self.doors["dual_door"]
        engaged = [sw.engaged_by for sw in self.switches.values()]
        if all(engaged) and not door.open:
            door.open = True
            self.synergy += 1
            await self.bus.emit(
                {
                    "type": "synergy",
                    "payload": {
                        "value": self.synergy,
                        "message": "双人机关启动！✨",
                    },
                }
            )
        elif not all(engaged):
            door.open = False

    async def pickup(self, agent_id: str, item_id: str) -> bool:
        agent = self.agents[agent_id]
        item = self.items[item_id]
        if item.held_by or item.pos != agent.pos:
            return False
        item.held_by = agent_id
        agent.inventory.append(item_id)
        await self.emit_world()
        return True

    async def drop(self, agent_id: str, item_id: str, pos: GridPos) -> bool:
        agent = self.agents[agent_id]
        if item_id not in agent.inventory:
            return False
        item = self.items[item_id]
        item.held_by = None
        item.pos = pos
        agent.inventory.remove(item_id)
        await self.emit_world()
        return True

    async def talk(self, agent_id: str, npc_id: str, text: str) -> str:
        npc = self.npcs[npc_id]
        if npc.requires_both:
            lan = self.agents["lan"].pos
            xia = self.agents["xia"].pos
            if lan != npc.pos or xia != npc.pos:
                return "要两个人一起到齐才说话。"
        if npc.gives_item:
            item = self.items[npc.gives_item]
            item.pos = npc.pos
        return npc.dialog[0]

    async def use_switch(self, agent_id: str, switch_id: str) -> None:
        switch = self.switches[switch_id]
        if self.agents[agent_id].pos == switch.pos:
            switch.engaged_by = agent_id
        await self.update_door_state()
        await self.emit_world()

    async def emit_ui_event(self, event_type: str, payload: dict) -> None:
        await self.bus.emit({"type": event_type, "payload": payload})

    def nearby(self, agent_id: str) -> dict:
        agent = self.agents[agent_id]
        ax, ay = agent.pos
        area = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                pos = (ax + dx, ay + dy)
                if self.in_bounds(pos):
                    area.append({"x": pos[0], "y": pos[1], "tile": self.tile_kind(pos)})
        npcs = [
            {
                "id": npc_id,
                "name": npc.name,
                "x": npc.pos[0],
                "y": npc.pos[1],
            }
            for npc_id, npc in self.npcs.items()
            if math.dist(npc.pos, agent.pos) <= 1.5
        ]
        items = [
            {
                "id": item_id,
                "name": item.name,
                "x": item.pos[0],
                "y": item.pos[1],
            }
            for item_id, item in self.items.items()
            if item.held_by is None and math.dist(item.pos, agent.pos) <= 1.5
        ]
        return {"tiles": area, "npcs": npcs, "items": items}
