# Pixel Duo Agents Demo

**一句话卖点：** “输入一句指令，看两位性格迥异的 AI 伙伴在像素世界里边走边聊、分工协作，把任务做成一场实时上演的小剧场。”

## 功能亮点
- 2D 俯视角像素网格世界（20x14，32px）
- 双 Agent（阿岚 / 小夏）协作执行指令
- 实时可解释流程面板（ThoughtSummary / Plan / Observation / Action / Dialogue）
- Pause / Step / Resume 控制回合式观看
- 3 个可演示任务 + `/help`
- 双人机关（双开关门）必须协作触发
- Streaming 事件流 + trace_id 显示

## 目录结构
```
backend/
  app.py            # FastAPI + SSE 事件流
  mission.py        # 任务脚本与执行控制
  agents.py         # OpenAI Agents SDK 解说层
  world.py          # 世界状态 / A* / 交互工具
  requirements.txt
frontend/
  index.html
  static/
    app.js
    styles.css
.env.example
```

## 一键启动
> 需要 Python 3.10+

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
cd ..
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000`。

也可以直接用 `package.json` 脚本：
```bash
npm run dev
```

## 环境变量
复制并填写 `.env`：
```
OPENAI_API_KEY=你的KEY
OPENAI_MODEL=gpt-4o-mini
```

## 玩法说明
1. 输入一句任务指令（或点击预设按钮）。
2. 双 Agent 会在地图中移动、交互、拾取物品。
3. 右侧面板滚动显示 ThoughtSummary / Plan / Observation / Action / Dialogue。
4. 点击 Pause / Step / Resume 像回合制 RPG 一样看协作过程。

## 架构说明
- **世界状态只在后端维护**：所有移动、对话、拾取都走工具函数（`world.py`）。
- **事件流**：后端通过 SSE 推送 `world_update` / `agent_event` / `synergy` 等事件。
- **Agents SDK**：`agents.py` 用 Agent + Runner 生成可解释摘要，并在前端显示 trace_id。

## 如何扩展
- **地图**：修改 `backend/world.py` 的 `layout` 和实体坐标。
- **任务**：在 `backend/mission.py` 里新增 `Mission` actions。
- **人物性格**：更新 `backend/agents.py` 中的 `AgentProfile`。

## 预设任务
- A 新手任务：买苹果 -> 送到家门口
- B 协作机关：分头取线索 -> 双人开关门 -> 拿钥匙 -> 交给守门 NPC
- C 轻喜剧：找走失小猫（脚印线索）

## 自测 Checklist
- [ ] 输入指令后，两位 Agent 同时行动并协作完成任务
- [ ] Pause / Step / Resume 有效
- [ ] 双人机关必须协作才能开启
- [ ] ThoughtSummary / Plan / Observation 显示简短可读
- [ ] 地图动画连续无瞬移
- [ ] API Key 仅后端读取，不暴露到前端
