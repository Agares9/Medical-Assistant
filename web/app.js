const homePage = document.querySelector("#homePage");
const qaPage = document.querySelector("#qaPage");
const agentsPage = document.querySelector("#agentsPage");
const safetyPage = document.querySelector("#safetyPage");
const knowledgePage = document.querySelector("#knowledgePage");
const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#questionInput");
const sendBtn = document.querySelector("#sendBtn");
const clearBtn = document.querySelector("#clearBtn");
const newSessionBtn = document.querySelector("#newSessionBtn");
const enterQaBtn = document.querySelector("#enterQaBtn");
const homeBtn = document.querySelector("#homeBtn");
const verifyOverlay = document.querySelector("#verifyOverlay");
const verifyForm = document.querySelector("#verifyForm");
const verifyInput = document.querySelector("#verifyInput");
const verifyError = document.querySelector("#verifyError");
const verifyCancelBtn = document.querySelector("#verifyCancelBtn");
const verifySubmitBtn = document.querySelector("#verifySubmitBtn");
const sessionLabel = document.querySelector("#sessionLabel");
const modeLabel = document.querySelector("#modeLabel");
const progressLabel = document.querySelector("#progressLabel");
const progressBar = document.querySelector("#progressBar");
const progressTrack = document.querySelector("#progressTrack");
const agentCount = document.querySelector("#agentCount");
const queueCount = document.querySelector("#queueCount");
const activeAgents = document.querySelector("#activeAgents");
const recentConversations = document.querySelector("#recentConversations");
const flowCaption = document.querySelector("#flowCaption");
const flowSteps = Array.from(document.querySelectorAll(".flow-step"));
const latencyBadges = Array.from(document.querySelectorAll("[data-latency]"));

const SESSION_KEY = "medix_web_session_id";
const AUTH_TOKEN_KEY = "medix_auth_token";
const PAGE_ELEMENTS = {
  home: homePage,
  agents: agentsPage,
  safety: safetyPage,
  knowledge: knowledgePage,
  qa: qaPage,
};
const VALID_PAGES = new Set(Object.keys(PAGE_ELEMENTS));
const STAGE_INDEX = {
  dispatch: 0,
  retrieval: 1,
  analysis: 2,
  safety: 3,
  reply: 4,
};
let currentPage = "home";
let pendingVerifiedAction = null;

function createSessionId() {
  return `web-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
}

function getSessionId() {
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = createSessionId();
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}

function setSessionId(sessionId) {
  localStorage.setItem(SESSION_KEY, sessionId);
  sessionLabel.textContent = `会话 ${sessionId.replace(/^web-/, "")}`;
}

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function setAuthToken(token) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

function hasLocalVerification() {
  return Boolean(getAuthToken());
}

function openVerification(action) {
  pendingVerifiedAction = action;
  verifyError.textContent = "";
  verifyInput.value = "";
  verifyOverlay.classList.remove("hidden");
  setTimeout(() => verifyInput.focus(), 0);
}

function closeVerification() {
  verifyOverlay.classList.add("hidden");
  verifyError.textContent = "";
  pendingVerifiedAction = null;
}

function runAfterVerification(action) {
  if (hasLocalVerification()) {
    action();
    return;
  }
  openVerification(action);
}

function pageFromLocation() {
  const page = location.hash.replace(/^#/, "");
  return VALID_PAGES.has(page) ? page : "home";
}

function showPage(page, options = {}) {
  const nextPage = VALID_PAGES.has(page) ? page : "home";
  if (nextPage === "qa" && !hasLocalVerification()) {
    openVerification(() => showPage("qa", options));
    return;
  }
  const { push = true } = options;
  if (push && nextPage !== currentPage) {
    history.pushState({ page: nextPage }, "", nextPage === "home" ? location.pathname : `#${nextPage}`);
  }
  currentPage = nextPage;
  const isQa = nextPage === "qa";
  Object.entries(PAGE_ELEMENTS).forEach(([name, element]) => {
    element.classList.toggle("hidden", name !== nextPage);
  });
  document.body.style.overflow = isQa ? "hidden" : "";
  if (isQa) {
    inputEl.focus();
  }
}

function appendMessage(role, content, options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${options.error ? " error" : ""}${options.loading ? " loading" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "你" : "M";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (options.loading) {
    bubble.innerHTML = `
      <div class="thinking-card">
        <span class="thinking-orb" aria-hidden="true"></span>
        <span class="thinking-copy">
          <strong>${content}</strong>
          <span>正在协调多个 Agent<span class="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span></span>
        </span>
      </div>
    `;
  } else {
    const text = document.createElement("p");
    text.textContent = content;
    bubble.appendChild(text);
  }

  if (options.meta && options.meta.length) {
    const meta = document.createElement("div");
    meta.className = "meta";
    options.meta.forEach((item) => {
      const span = document.createElement("span");
      span.textContent = item;
      meta.appendChild(span);
    });
    bubble.appendChild(meta);
  }

  article.appendChild(avatar);
  article.appendChild(bubble);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return article;
}

function setActiveAgentRows(rows) {
  activeAgents.innerHTML = "";
  rows.forEach((row, index) => {
    const li = document.createElement("li");
    const dot = document.createElement("i");
    dot.className = index === 0 ? "ok" : index === 1 ? "info" : index === 2 ? "warn" : "muted";

    const name = document.createElement("strong");
    name.textContent = row.name;

    const state = document.createElement("span");
    state.textContent = row.state;

    li.append(dot, name, state);
    activeAgents.appendChild(li);
  });
}

function setFlowState(index, caption) {
  flowSteps.forEach((step, stepIndex) => {
    step.classList.toggle("done", stepIndex < index);
    step.classList.toggle("active", stepIndex === index);
    step.classList.remove("pending");
  });
  flowCaption.textContent = caption;
}

function applyProgress(progress = {}) {
  const stage = progress.stage || "dispatch";
  const index = STAGE_INDEX[stage] ?? 0;
  const percent = Number.isFinite(Number(progress.percent)) ? Number(progress.percent) : 0;
  const label = progress.label || "后端处理中";

  setFlowState(index, label);
  progressTrack.classList.remove("indeterminate");
  progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  progressLabel.textContent = percent >= 100 ? "完成" : `${Math.round(percent)}%`;

  if (progress.mode) {
    modeLabel.textContent = progress.mode;
  }

  if (Array.isArray(progress.agents) && progress.agents.length) {
    setActiveAgentRows(progress.agents.map((agent) => ({
      name: agent.name || "Agent",
      state: agent.state || "执行中",
    })));
    agentCount.textContent = String(progress.agents.length);
  }
}

function setIdleStatus() {
  modeLabel.textContent = "协作";
  progressLabel.textContent = "待命";
  progressTrack.classList.remove("indeterminate");
  progressBar.style.width = "0%";
  queueCount.textContent = "0";
  agentCount.textContent = "5";
  setFlowState(0, "等待问题输入");
}

function setSendButton(label) {
  sendBtn.innerHTML = `${label} <span class="mini-icon arrow-icon" aria-hidden="true"></span>`;
}

function updateStatus(result) {
  const swarmEnabled = Boolean(result.swarm_enabled);
  modeLabel.textContent = swarmEnabled ? "协作" : "单 Agent";
  queueCount.textContent = swarmEnabled ? "2" : "0";
  progressLabel.textContent = "完成";
  progressTrack.classList.remove("indeterminate");
  progressBar.style.width = "100%";
  flowSteps.forEach((step) => {
    step.classList.add("done");
    step.classList.remove("active", "pending");
  });
  flowCaption.textContent = "回答已生成";

  const agents = Array.isArray(result.agents_involved) && result.agents_involved.length
    ? result.agents_involved
    : result.agent_id
      ? [result.agent_id]
      : [];

  agentCount.textContent = agents.length ? String(agents.length) : swarmEnabled ? "3" : "1";

  if (agents.length) {
    setActiveAgentRows(agents.map((name, index) => ({
      name,
      state: index === agents.length - 1 ? "已完成" : "协作完成",
    })));
  }
}

function setProcessingStatus() {
  modeLabel.textContent = "协作";
  progressLabel.textContent = "3%";
  progressTrack.classList.remove("indeterminate");
  progressBar.style.width = "3%";
  queueCount.textContent = "1";
  agentCount.textContent = "1";
  setFlowState(0, "任务已提交，等待后端接收");
  setActiveAgentRows([
    { name: "Web API", state: "排队" },
  ]);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function refreshRuntimeLatencies() {
  latencyBadges.forEach((badge) => {
    const min = Number(badge.dataset.min || 80);
    const max = Number(badge.dataset.max || 600);
    badge.textContent = `${randomInt(min, max)}ms`;
  });
}

function formatRecentTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diffMs < minute) return "刚刚";
  if (diffMs < hour) return `${Math.floor(diffMs / minute)}分钟前`;
  if (diffMs < day) return `${Math.floor(diffMs / hour)}小时前`;
  return `${Math.floor(diffMs / day)}天前`;
}

function renderRecentConversations(items) {
  recentConversations.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-history";
    empty.textContent = "暂无历史对话";
    recentConversations.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.question = item.question || item.title || "";
    button.innerHTML = `
      <span class="mini-icon message-icon" aria-hidden="true"></span>
      ${item.title || "未命名对话"}
      <span>${formatRecentTime(item.created_at)}</span>
    `;
    button.addEventListener("click", () => {
      runAfterVerification(() => {
        showPage("qa");
        inputEl.value = item.question || "";
        inputEl.focus();
      });
    });
    recentConversations.appendChild(button);
  });
}

async function loadRecentConversations() {
  try {
    const response = await fetch("/api/conversations/recent?limit=8", {
      headers: { "Accept": "application/json" },
    });
    const result = await response.json();
    if (response.ok && Array.isArray(result.items)) {
      renderRecentConversations(result.items);
    }
  } catch (error) {
    renderRecentConversations([]);
  }
}

async function pollTask(taskId, loadingMessage) {
  let lastStatus = null;

  for (let attempt = 0; attempt < 360; attempt += 1) {
    const response = await fetch(`/api/chat/status/${taskId}`, {
      headers: { "Accept": "application/json" },
    });
    const task = await response.json();

    if (!response.ok) {
      throw new Error(task.error || "状态查询失败");
    }

    lastStatus = task.status;
    applyProgress(task.progress);

    if (task.status === "completed" || task.status === "failed") {
      loadingMessage.remove();
      const result = task.result || {};
      if (task.status === "failed" || result.error) {
        appendMessage("assistant", result.answer || result.error || task.error || "请求失败", { error: true });
      } else {
        const meta = [];
        if (result.swarm_enabled) meta.push("Swarm");
        if (result.total_time) meta.push(`${Number(result.total_time).toFixed(1)} 秒`);
        if (result.iterations) meta.push(`${result.iterations} 轮`);
        appendMessage("assistant", result.answer || "未返回回答", { meta });
        updateStatus(result);
        loadRecentConversations();
      }
      return;
    }

    await sleep(500);
  }

  throw new Error(`任务超时，最后状态：${lastStatus || "未知"}`);
}

async function sendQuestion(question) {
  if (!hasLocalVerification()) {
    openVerification(() => sendQuestion(question));
    return;
  }
  showPage("qa", { push: currentPage !== "qa" });
  const sessionId = getSessionId();
  appendMessage("user", question);
  inputEl.value = "";
  inputEl.focus();

  const loadingMessage = appendMessage("assistant", "正在分析，请稍候", { loading: true });
  sendBtn.disabled = true;
  setSendButton("处理中");
  setProcessingStatus();

  try {
    const response = await fetch("/api/chat/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId, auth_token: getAuthToken() }),
    });

    const task = await response.json();

    if (!response.ok) {
      loadingMessage.remove();
      if (task.error === "not_verified") {
        clearAuthToken();
        openVerification(() => sendQuestion(question));
        return;
      }
      appendMessage("assistant", task.answer || task.error || "请求失败", { error: true });
      return;
    }

    await pollTask(task.task_id, loadingMessage);
  } catch (error) {
    loadingMessage.remove();
    appendMessage("assistant", `请求失败：${error.message}`, { error: true });
  } finally {
    progressTrack.classList.remove("indeterminate");
    sendBtn.disabled = false;
    setSendButton("发送");
  }
}

async function submitVerification() {
  const sessionId = getSessionId();
  const answer = verifyInput.value.trim();
  verifySubmitBtn.disabled = true;
  verifySubmitBtn.textContent = "验证中";
  verifyError.textContent = "";

  try {
    const response = await fetch("/api/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, answer }),
    });
    const result = await response.json();

    if (!response.ok || !result.verified) {
      verifyError.textContent = result.message || "验证失败";
      verifyInput.select();
      return;
    }

    setSessionId(result.session_id);
    setAuthToken(result.auth_token);
    const action = pendingVerifiedAction;
    closeVerification();
    if (action) action();
  } catch (error) {
    verifyError.textContent = `验证请求失败：${error.message}`;
  } finally {
    verifySubmitBtn.disabled = false;
    verifySubmitBtn.textContent = "验证";
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = inputEl.value.trim();
  if (question) sendQuestion(question);
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;

  if (event.shiftKey) {
    return;
  }

  if (!event.isComposing) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

clearBtn.addEventListener("click", () => {
  inputEl.value = "";
  inputEl.focus();
});

newSessionBtn.addEventListener("click", () => {
  setSessionId(createSessionId());
  messagesEl.innerHTML = "";
  appendMessage("assistant", "已开始新会话。请描述问题。");
  setIdleStatus();
});

enterQaBtn.addEventListener("click", () => runAfterVerification(() => showPage("qa")));
homeBtn.addEventListener("click", () => {
  showPage("home");
});

document.querySelectorAll("[data-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.target;
    if (target === "qa") {
      runAfterVerification(() => showPage("qa"));
      return;
    }
    showPage(target);
  });
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    runAfterVerification(() => {
      showPage("qa");
      inputEl.value = button.dataset.question || "";
      inputEl.focus();
    });
  });
});

verifyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitVerification();
});

verifyCancelBtn.addEventListener("click", closeVerification);

setSessionId(getSessionId());
history.replaceState({ page: pageFromLocation() }, "", location.href);
window.addEventListener("popstate", () => {
  showPage(pageFromLocation(), { push: false });
});
showPage(pageFromLocation(), { push: false });
setIdleStatus();
refreshRuntimeLatencies();
loadRecentConversations();
setInterval(refreshRuntimeLatencies, 1000);
