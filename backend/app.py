from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .mission import MissionRunner
from .world import EventBus, World

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI()

bus = EventBus()
world = World(bus)
mission_runner = MissionRunner(world, bus)


@app.on_event("startup")
async def startup() -> None:
    await world.emit_world()


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    queue = bus.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/command")
async def command(payload: dict) -> dict:
    text = payload.get("text", "")
    mission_id = payload.get("mission_id", "task_a")
    if text.strip() == "/help":
        await bus.emit(
            {
                "type": "help",
                "payload": {
                    "text": "输入一句任务指令或点击预设任务按钮。支持 /help 查看说明。",
                },
            }
        )
        return {"ok": True}
    mission_runner.start(mission_id)
    await bus.emit(
        {
            "type": "command",
            "payload": {"text": text, "mission_id": mission_id},
        }
    )
    return {"ok": True}


@app.post("/control")
async def control(payload: dict) -> dict:
    action = payload.get("action")
    if action == "pause":
        mission_runner.pause()
    elif action == "resume":
        mission_runner.resume()
    elif action == "step":
        mission_runner.step()
    return {"ok": True}


@app.get("/world")
async def get_world() -> dict:
    return world.serialize()


app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
