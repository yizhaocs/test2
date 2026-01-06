const canvas = document.getElementById("worldCanvas");
const ctx = canvas.getContext("2d");
const TILE_SIZE = 32;

const state = {
  world: null,
  agents: {},
  targets: {},
  logs: {
    overview: [],
    lan: [],
    xia: [],
    world: [],
  },
  progress: 0,
};

const colors = {
  grass: "#1e293b",
  wall: "#334155",
  water: "#0ea5e9",
  shop: "#f59e0b",
  home: "#22c55e",
  switch: "#f97316",
  doorClosed: "#7c3aed",
  doorOpen: "#a78bfa",
};

function drawWorld() {
  if (!state.world) return;
  const { width, height } = state.world;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const tile = getTileKind(x, y);
      ctx.fillStyle = colors.grass;
      if (tile === "wall") ctx.fillStyle = colors.wall;
      if (tile === "water") ctx.fillStyle = colors.water;
      if (tile === "shop") ctx.fillStyle = colors.shop;
      if (tile === "home") ctx.fillStyle = colors.home;
      if (tile === "switch") ctx.fillStyle = colors.switch;
      if (tile === "door") {
        const door = state.world.doors["dual_door"];
        ctx.fillStyle = door.open ? colors.doorOpen : colors.doorClosed;
      }
      ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
    }
  }

  Object.values(state.world.items).forEach((item) => {
    ctx.fillStyle = "#fde68a";
    ctx.fillRect(item.x * TILE_SIZE + 8, item.y * TILE_SIZE + 8, 16, 16);
  });

  Object.values(state.world.npcs).forEach((npc) => {
    ctx.fillStyle = "#e879f9";
    ctx.fillRect(npc.x * TILE_SIZE + 6, npc.y * TILE_SIZE + 6, 20, 20);
  });

  Object.entries(state.agents).forEach(([id, agent]) => {
    ctx.fillStyle = id === "lan" ? "#38bdf8" : "#fb7185";
    ctx.fillRect(agent.x - 12, agent.y - 12, 24, 24);
    ctx.fillStyle = "#f8fafc";
    ctx.font = "10px sans-serif";
    ctx.fillText(agent.name, agent.x - 16, agent.y - 18);
  });

  requestAnimationFrame(drawWorld);
}

function getTileKind(x, y) {
  return state.world?.tiles?.[`${x},${y}`] || "grass";
}

function updateWorld(data) {
  const tiles = {};
  for (let y = 0; y < data.height; y++) {
    for (let x = 0; x < data.width; x++) {
      tiles[`${x},${y}`] = data.grid?.[y]?.[x] || data.tileKinds?.[`${x},${y}`] || "grass";
    }
  }
  state.world = { ...data, tiles };
  Object.entries(data.agents).forEach(([id, agent]) => {
    if (!state.agents[id]) {
      state.agents[id] = { name: agent.name, x: agent.x * TILE_SIZE + 16, y: agent.y * TILE_SIZE + 16 };
    }
    const target = { x: agent.x * TILE_SIZE + 16, y: agent.y * TILE_SIZE + 16 };
    state.targets[id] = target;
  });
}

function animateAgents() {
  Object.entries(state.targets).forEach(([id, target]) => {
    const agent = state.agents[id];
    if (!agent) return;
    agent.x += (target.x - agent.x) * 0.2;
    agent.y += (target.y - agent.y) * 0.2;
  });
  requestAnimationFrame(animateAgents);
}

function addLog(tab, payload) {
  const entry = { time: new Date().toLocaleTimeString(), ...payload };
  state.logs[tab].unshift(entry);
  renderLogs(tab);
}

function renderLogs(tab) {
  const container = document.getElementById(tab);
  if (!container) return;
  container.innerHTML = "";
  state.logs[tab].slice(0, 20).forEach((item) => {
    const card = document.createElement("div");
    card.className = "log-card";
    const title = document.createElement("h3");
    title.textContent = `${item.title || "事件"} · ${item.time}`;
    card.appendChild(title);
    if (item.thought) {
      const p = document.createElement("p");
      p.textContent = `🧠 ${item.thought}`;
      card.appendChild(p);
    }
    if (item.plan?.length) {
      const ul = document.createElement("ul");
      item.plan.forEach((step) => {
        const li = document.createElement("li");
        li.textContent = step;
        ul.appendChild(li);
      });
      card.appendChild(ul);
    }
    if (item.observation) {
      const p = document.createElement("p");
      p.textContent = `👀 ${item.observation}`;
      card.appendChild(p);
    }
    if (item.action) {
      const p = document.createElement("p");
      p.textContent = `🧩 ${item.action}`;
      card.appendChild(p);
    }
    if (item.dialogue) {
      const p = document.createElement("p");
      p.textContent = `💬 ${item.dialogue}`;
      card.appendChild(p);
    }
    if (item.text) {
      const p = document.createElement("p");
      p.textContent = item.text;
      card.appendChild(p);
    }
    container.appendChild(card);
  });
}

function updateProgress(status) {
  if (status === "start") {
    state.progress = 0;
  }
  if (status === "complete") {
    state.progress = 100;
  }
  document.getElementById("progressFill").style.width = `${state.progress}%`;
}

const source = new EventSource("/events");
source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "world_update") {
    updateWorld(data.payload);
  }
  if (data.type === "agent_event") {
    const payload = data.payload;
    const tab = payload.agent_id === "lan" ? "lan" : "xia";
    addLog(tab, {
      title: payload.agent_id === "lan" ? "阿岚" : "小夏",
      thought: payload.ThoughtSummary,
      plan: payload.Plan,
      observation: payload.Observation,
      action: payload.Action,
      dialogue: payload.Dialogue,
    });
    addLog("overview", {
      title: payload.agent_id === "lan" ? "阿岚" : "小夏",
      thought: payload.ThoughtSummary,
      plan: payload.Plan,
      observation: payload.Observation,
      action: payload.Action,
      dialogue: payload.Dialogue,
    });
  }
  if (data.type === "agent_stream") {
    addLog("world", { title: "Agent Stream", text: data.payload.text });
  }
  if (data.type === "task_status") {
    addLog("world", { title: "任务状态", text: `${data.payload.title} - ${data.payload.status}` });
    updateProgress(data.payload.status);
  }
  if (data.type === "command") {
    addLog("world", { title: "指令", text: data.payload.text });
  }
  if (data.type === "help") {
    addLog("world", { title: "帮助", text: data.payload.text });
  }
  if (data.type === "synergy") {
    document.getElementById("synergyValue").textContent = data.payload.value;
    addLog("world", { title: "默契值+1", text: data.payload.message });
  }
  if (data.type === "trace") {
    document.getElementById("traceId").textContent = data.payload.trace_id;
  }
};

const tabs = document.querySelectorAll(".tabs button");
const contents = document.querySelectorAll(".tab-content");

function activateTab(tabId) {
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabId));
  contents.forEach((content) => content.classList.toggle("hidden", content.id !== tabId));
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

async function sendCommand(text, missionId) {
  await fetch("/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, mission_id: missionId }),
  });
}

async function sendControl(action) {
  await fetch("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

document.getElementById("sendCommand").addEventListener("click", () => {
  const input = document.getElementById("commandInput");
  sendCommand(input.value || "执行预设任务", "task_a");
});

document.querySelectorAll(".preset").forEach((btn) => {
  btn.addEventListener("click", () => {
    sendCommand(btn.textContent, btn.dataset.mission);
  });
});

document.getElementById("pauseBtn").addEventListener("click", () => sendControl("pause"));
document.getElementById("resumeBtn").addEventListener("click", () => sendControl("resume"));
document.getElementById("stepBtn").addEventListener("click", () => sendControl("step"));

updateWorld({
  width: 20,
  height: 14,
  agents: {},
  items: {},
  doors: { dual_door: { open: false } },
  tileKinds: {},
});

animateAgents();
drawWorld();
