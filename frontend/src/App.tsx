import { FormEvent, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import type { AgentProgress, ChatMessage, ChatResult, ChatTask, Page, RecentConversation } from "./types";

const SESSION_KEY = "medix_web_session_id";
const AUTH_TOKEN_KEY = "medix_auth_token";
const pages: Page[] = ["home", "agents", "safety", "knowledge", "qa"];
const stageIndex: Record<string, number> = { dispatch: 0, retrieval: 1, analysis: 2, safety: 3, reply: 4 };

function createSessionId() {
  return `web-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
}

function createMessageId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `msg-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
}

function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pageFromHash(): Page {
  const hash = window.location.hash.replace(/^#/, "") as Page;
  return pages.includes(hash) ? hash : "home";
}

function formatRecentTime(value?: string) {
  if (!value) return "";
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

function MiniIcon({ name }: { name: string }) {
  return <span className={`mini-icon ${name}-icon`} aria-hidden="true" />;
}

function Brand({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="nav-brand">
      <div className="brand-mark image-mark"><img src="/icon.png" alt="MediX" /></div>
      <div><strong>{title}</strong><span>{subtitle}</span></div>
    </div>
  );
}

function NavButton({ target, children, onNavigate }: { target: Page; children: ReactNode; onNavigate: (page: Page) => void }) {
  return <button type="button" onClick={() => onNavigate(target)}>{children}</button>;
}

function RuntimeRows() {
  const ranges = useMemo(() => [
    { dot: "ok", name: "Supervisor", state: "routing", min: 55, max: 180 },
    { dot: "info", name: "Medical RAG", state: "retrieving guideline snippets", min: 180, max: 680 },
    { dot: "warn", name: "Safety Guard", state: "checking contraindications", min: 90, max: 360 },
    { dot: "violet", name: "Response Writer", state: "streaming answer draft", min: 120, max: 520 },
  ], []);
  const [values, setValues] = useState(() => ranges.map((item) => randomInt(item.min, item.max)));

  useEffect(() => {
    const timer = window.setInterval(() => {
      setValues(ranges.map((item) => randomInt(item.min, item.max)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [ranges]);

  return (
    <div className="runtime-rows" aria-label="模拟 Agent 延迟">
      {ranges.map((row, index) => (
        <div key={row.name}>
          <span className={row.dot}></span><strong>{row.name}</strong><em>{row.state}</em><b>{values[index]}ms</b>
        </div>
      ))}
    </div>
  );
}

function HomePage({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return (
    <section className="page home-page" aria-label="MediX 首页">
      <div className="ambient-layer" aria-hidden="true">
        <div className="glow glow-teal"></div><div className="glow glow-blue"></div><div className="glow glow-green"></div>
        <div className="data-field">{Array.from({ length: 12 }).map((_, i) => <span key={i}></span>)}</div>
      </div>
      <nav className="home-nav" aria-label="主导航">
        <Brand title="Medix Swarm" subtitle="Medical Agent Runtime" />
        <div className="nav-links">
          <NavButton target="agents" onNavigate={onNavigate}><MiniIcon name="pulse" />Agent 状态</NavButton>
          <NavButton target="safety" onNavigate={onNavigate}><MiniIcon name="shield" />安全审查</NavButton>
          <NavButton target="knowledge" onNavigate={onNavigate}><MiniIcon name="book" />知识库</NavButton>
        </div>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Multi-Agent Medical Copilot</p>
          <h1>智能医药助手</h1>
          <h2>让多个 Agent 协同完成问答</h2>
          <p className="hero-text">从症状理解、医学知识检索、用药安全审查到最终回复生成，每一步都可追踪、可解释、可回放。</p>
          <div className="hero-actions">
            <button className="primary-cta" type="button" onClick={() => onNavigate("qa")}>进入问答页面 <MiniIcon name="arrow" /></button>
          </div>
          <p className="route-hint">进入问答工作台后可查看实时 Agent 流程</p>
        </div>
        <aside className="runtime-console" aria-label="Agent Runtime">
          <div className="console-topbar"><span></span><span></span><span></span><strong>Agent Runtime / Live</strong><em>LIVE</em></div>
          <div className="orbit-stage" aria-hidden="true">
            <div className="orbit orbit-outer"></div><div className="orbit orbit-mid"></div><div className="core-node">AI</div>
            <div className="agent-node node-dispatch">调度</div><div className="agent-node node-retrieval">检索</div>
            <div className="agent-node node-analysis">分析</div><div className="agent-node node-safety">安全</div><div className="agent-node node-answer">回复</div>
          </div>
          <RuntimeRows />
        </aside>
      </section>
      <section className="home-stats" aria-label="系统状态"><div><strong>5</strong><span>Agents</span></div><div><strong>24/7</strong><span>Safety</span></div><div><strong>0</strong><span>Blocked</span></div></section>
    </section>
  );
}

function InfoPage({ kind, onNavigate }: { kind: "agents" | "safety" | "knowledge"; onNavigate: (page: Page) => void }) {
  const config = {
    agents: {
      title: "Agent 状态", sub: "Runtime Overview", eyebrow: "Agent Runtime", heading: "当前多智能体运行状态",
      cards: [
        ["LeadAgent", "负责问题复杂度判断、任务拆分和最终汇总。", "Ready"],
        ["ConsultationAgent", "处理通用健康咨询、生活方式建议和常见问题答复。", "Ready"],
        ["DiagnosticAgent", "负责症状模式分析、风险分级和鉴别诊断思路。", "Ready"],
        ["ResearchAgent", "检索临床指南、循证资料和深度研究结果。", "Ready"],
      ],
    },
    safety: {
      title: "安全审查", sub: "Medical Guardrails", eyebrow: "Safety Review", heading: "医疗输出约束与风险提示",
      cards: [
        ["免责声明检查", "回答会补充“不能替代专业医生诊断和治疗”的安全提示。", "Enabled"],
        ["高危症状提醒", "胸痛、呼吸困难、意识障碍等问题会优先提示及时就医。", "Enabled"],
        ["约束验证", "运行时读取 YAML 约束，对 Agent 能力边界和输出进行校验。", "Enabled"],
        ["自动修复", "当回答缺少关键安全提示时，自动补全结构化说明。", "Enabled"],
      ],
    },
    knowledge: {
      title: "知识库", sub: "Milvus Medical RAG", eyebrow: "Knowledge Base", heading: "本地医学知识库概览",
      cards: [
        ["Milvus Lite", "本地 collection: medical_knowledge，使用 512 维中文向量模型。", "Loaded"],
        ["生活方式文档", "包含高血压、糖尿病、感冒和通用健康生活方式建议。", "4 files"],
        ["ICD 与临床路径", "支持 ICD-11 预览资料和按科室清洗后的临床路径资料。", "Prepared"],
        ["临床指南", "包含高血压和糖尿病指南资料，供 Agent 检索引用。", "2 files"],
      ],
    },
  }[kind];

  return (
    <section className="page info-page" aria-label={`${config.title}页面`}>
      <nav className="home-nav info-nav">
        <Brand title={config.title} subtitle={config.sub} />
        <div className="nav-links"><NavButton target="home" onNavigate={onNavigate}>首页</NavButton><NavButton target="qa" onNavigate={onNavigate}>问答</NavButton></div>
      </nav>
      <section className="info-content">
        <p className="eyebrow">{config.eyebrow}</p><h1>{config.heading}</h1>
        <div className="info-grid">{config.cards.map(([title, copy, state], index) => <article key={title}><span className={`status-dot ${["ok", "info", "warn", "violet"][index]}`}></span><h2>{title}</h2><p>{copy}</p><strong>{state}</strong></article>)}</div>
      </section>
    </section>
  );
}

function QaPage(props: {
  sessionId: string;
  progress: AgentProgress;
  messages: ChatMessage[];
  recent: RecentConversation[];
  question: string;
  sending: boolean;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  onNewSession: () => void;
  onHome: () => void;
  onRecent: (question: string) => void;
}) {
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [waitingSeconds, setWaitingSeconds] = useState(0);
  const percent = Math.max(0, Math.min(100, Number(props.progress.percent ?? 0)));
  const activeIndex = stageIndex[props.progress.stage || "dispatch"] ?? 0;
  const agents = props.progress.agents?.length ? props.progress.agents : [
    { name: "Supervisor", state: "编排中" }, { name: "Medical RAG", state: "检索知识库" },
    { name: "Safety Guard", state: "审查风险" }, { name: "Response Writer", state: "等待输入" },
  ];

  useEffect(() => { messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight }); }, [props.messages]);
  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => {
    if (!props.sending) {
      setWaitingSeconds(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      setWaitingSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [props.sending]);

  const submit = (event: FormEvent) => { event.preventDefault(); props.onSubmit(); };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      props.onSubmit();
    }
  };

  return (
    <section className="page qa-page" aria-label="医疗问答页面">
      <aside className="agent-sidebar" aria-label="Agent 状态">
        <div className="qa-brand"><div className="brand-mark image-mark"><img src="/icon.png" alt="MediX" /></div><div><img className="brand-title-img" src="/brand-title.png" alt="智能医药助手" /><p>Medix Agent Swarm</p></div></div>
        <div className="sidebar-scroll">
        <section className="agent-card">
          <div className="card-title"><h2><MiniIcon name="pulse" />当前 Agent 状态</h2><span className="status-chip"><i></i>运行中</span></div>
          <p>任务: 多 Agent 医疗问答编排</p>
          <div className="progress-meta"><span>执行进度</span><strong>{percent >= 100 ? "完成" : percent ? `${Math.round(percent)}%` : "待命"}</strong></div>
          <div className="progress-track"><span style={{ width: `${percent}%` }}></span></div>
          <small>最近心跳 12 秒前 / 无阻塞</small>
        </section>
        <section className="orchestration-card"><h2><MiniIcon name="network" />项目编排</h2><div className="metric-grid"><div><strong>{agents.length || 5}</strong><span>Agents</span></div><div><strong>{props.progress.mode || "协作"}</strong><span>模式</span></div><div><strong>{props.sending ? 1 : 0}</strong><span>队列</span></div></div></section>
        <section className="flow-card">
          <div className="card-title"><h2><MiniIcon name="flow" />Agent 流程图</h2><span>Supervisor 模式</span></div>
          <div className="agent-flow" aria-label="Agent 执行流程">
            {[
              ["调度", "Supervisor"], ["检索", "Medical RAG"], ["分析", "Diagnostic"], ["安全", "Guard"], ["回复", "Writer"],
            ].map(([title, sub], index) => <div key={title} className={`flow-step ${index < activeIndex ? "done" : ""} ${index === activeIndex ? "active" : ""}`}><i></i><strong>{title}</strong><span>{sub}</span></div>)}
          </div>
          <p>{props.progress.label || "等待问题输入"}</p>
        </section>
        <section className="active-card"><h2><MiniIcon name="agent" />活跃 Agents</h2><ul>{agents.map((agent, index) => <li key={`${agent.name}-${index}`}><i className={index === 0 ? "ok" : index === 1 ? "info" : index === 2 ? "warn" : "muted"}></i><strong>{agent.name || "Agent"}</strong><span>{agent.state || "执行中"}</span></li>)}</ul></section>
        <section className="history-card"><h2><MiniIcon name="history" />最近对话</h2><div className="recent-conversations">{props.recent.length ? props.recent.map((item) => <button key={item.id || item.created_at || item.title} type="button" onClick={() => props.onRecent(item.question || "")}><MiniIcon name="message" />{item.title || "未命名对话"}<span>{formatRecentTime(item.created_at)}</span></button>) : <p className="empty-history">暂无历史对话</p>}</div></section>
        </div>
        <footer className="doctor-footer"><div className="doctor-avatar">张医</div><div><strong>张医生 (测试账号)</strong><span>呼吸内科 / 副主任医师</span></div><button type="button" title="返回首页" aria-label="返回首页" onClick={props.onHome}><MiniIcon name="home" /><span>首页</span></button></footer>
      </aside>
      <section className="chat-workspace" aria-label="医疗问答">
        <header className="chat-header"><div><h2>医疗咨询</h2><p>输入症状、病史或健康问题，系统会自动选择单 Agent 或 Swarm 协作。</p></div><button className="icon-button" type="button" title="新会话" aria-label="新会话" onClick={props.onNewSession}>+</button></header>
        <div ref={messagesRef} className="messages" aria-live="polite">
          {props.messages.map((message) => <article key={message.id} className={`message ${message.role}${message.error ? " error" : ""}${message.loading ? " loading" : ""}`}><div className="avatar">{message.role === "user" ? "你" : "M"}</div><div className="bubble">{message.loading ? <div className="thinking-card"><span className="thinking-orb" aria-hidden="true"></span><span className="thinking-copy"><strong>{message.content}</strong><span>正在协调多个 Agent<span className="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span></span>{waitingSeconds >= 15 ? <small className="patience-note">多 Agent 正在努力分析，需要一些时间，请耐心等待。</small> : null}</span></div> : <p>{message.content}</p>}{message.meta?.length ? <div className="meta">{message.meta.map((item) => <span key={item}>{item}</span>)}</div> : null}</div></article>)}
        </div>
        <form className="composer" onSubmit={submit}>
          <textarea ref={inputRef} rows={3} placeholder="例如：病人说身上长了奇怪的皮疹有点痒，可能是怎么回事" value={props.question} onChange={(event) => props.onQuestionChange(event.target.value)} onKeyDown={onKeyDown}></textarea>
          <div className="composer-actions"><span>会话 {props.sessionId.replace(/^web-/, "")}</span><button className="secondary-button" type="button" onClick={() => props.onQuestionChange("")}>清空输入</button><button className="primary-button" type="submit" disabled={props.sending}>{props.sending ? "处理中" : "发送"} <MiniIcon name="arrow" /></button></div>
        </form>
      </section>
    </section>
  );
}

function VerifyDialog({ open, onCancel, onVerified }: { open: boolean; onCancel: () => void; onVerified: (answer: string) => Promise<void> }) {
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open) { setAnswer(""); setError(""); window.setTimeout(() => inputRef.current?.focus(), 0); } }, [open]);
  if (!open) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await onVerified(answer.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
      inputRef.current?.select();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="verify-overlay" role="dialog" aria-modal="true" aria-labelledby="verifyTitle">
      <form className="verify-dialog" onSubmit={submit}>
        <div className="verify-mark"><img src="/icon.png" alt="MediX" /></div><p className="eyebrow">Access Verification</p><h2 id="verifyTitle">验证确认</h2>
        <p className="verify-copy">补全作者姓名：<strong className="name-prompt">亢*<span className="name-slot" aria-hidden="true"></span></strong></p>
        <label className="verify-field"><span>输入最后一个字</span><input ref={inputRef} type="text" maxLength={1} autoComplete="off" value={answer} onChange={(event) => setAnswer(event.target.value)} /></label>
        <p className="verify-error" aria-live="polite">{error}</p>
        <div className="verify-actions"><button className="secondary-button" type="button" onClick={onCancel}>取消</button><button className="primary-button" type="submit" disabled={submitting}>{submitting ? "验证中" : "验证"}</button></div>
      </form>
    </div>
  );
}

export function App() {
  const [page, setPage] = useState<Page>(() => pageFromHash());
  const [sessionId, setSessionIdState] = useState(() => localStorage.getItem(SESSION_KEY) || createSessionId());
  const [authToken, setAuthTokenState] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY) || "");
  const [verifyOpen, setVerifyOpen] = useState(false);
  const authTokenRef = useRef(authToken);
  const pendingAction = useRef<(() => void) | null>(null);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState<AgentProgress>({ stage: "dispatch", label: "等待问题输入", percent: 0, mode: "协作" });
  const [recent, setRecent] = useState<RecentConversation[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: "welcome", role: "assistant", content: "请描述问题。可以包含年龄、症状持续时间、伴随症状、既往病史和用药情况。" }]);

  const setSessionId = (value: string) => {
    localStorage.setItem(SESSION_KEY, value);
    setSessionIdState(value);
  };
  const setAuthToken = (value: string) => {
    localStorage.setItem(AUTH_TOKEN_KEY, value);
    setAuthTokenState(value);
    authTokenRef.current = value;
  };
  const clearAuthToken = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setAuthTokenState("");
    authTokenRef.current = "";
  };
  const appendMessage = (message: Omit<ChatMessage, "id">) => setMessages((items) => [...items, { ...message, id: createMessageId() }]);

  const navigate = (next: Page, push = true) => {
    if (next === "qa" && !authTokenRef.current) {
      pendingAction.current = () => navigate("qa", true);
      setVerifyOpen(true);
      return;
    }
    if (push && next !== page) history.pushState({ page: next }, "", next === "home" ? location.pathname : `#${next}`);
    setPage(next);
    document.body.style.overflow = next === "qa" ? "hidden" : "";
  };

  const loadRecent = async () => {
    try {
      const response = await fetch("/api/conversations/recent?limit=8", { headers: { Accept: "application/json" } });
      const result = await response.json();
      setRecent(response.ok && Array.isArray(result.items) ? result.items : []);
    } catch {
      setRecent([]);
    }
  };

  useEffect(() => {
    setSessionId(sessionId);
    history.replaceState({ page: pageFromHash() }, "", location.href);
    const onPop = () => navigate(pageFromHash(), false);
    window.addEventListener("popstate", onPop);
    loadRecent();
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const verify = async (answer: string) => {
    const response = await fetch("/api/auth/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, answer }) });
    const result = await response.json();
    if (!response.ok || !result.verified) throw new Error(result.message || "验证失败");
    setSessionId(result.session_id);
    setAuthToken(result.auth_token);
    setVerifyOpen(false);
    const action = pendingAction.current;
    pendingAction.current = null;
    action?.();
  };

  const updateStatus = (result: ChatResult) => {
    const agents = result.agents_involved?.length ? result.agents_involved.map((name, index) => ({ name, state: index === (result.agents_involved?.length || 1) - 1 ? "已完成" : "协作完成" })) : [{ name: result.agent_id || "Response Writer", state: "完成" }];
    setProgress({ stage: "reply", label: "回答已生成", percent: 100, mode: result.swarm_enabled ? "协作" : "单 Agent", agents });
  };

  const pollTask = async (taskId: string, loadingId: string) => {
    let lastStatus = "";
    for (let attempt = 0; attempt < 360; attempt += 1) {
      const response = await fetch(`/api/chat/status/${taskId}`, { headers: { Accept: "application/json" } });
      const task = await response.json() as ChatTask;
      if (!response.ok) throw new Error(task.error || "状态查询失败");
      lastStatus = task.status;
      if (task.progress) setProgress(task.progress);
      if (task.status === "completed" || task.status === "failed") {
        setMessages((items) => items.filter((item) => item.id !== loadingId));
        const result = task.result || {};
        if (task.status === "failed" || result.error) {
          appendMessage({ role: "assistant", content: result.answer || result.error || task.error || "请求失败", error: true });
        } else {
          const meta: string[] = [];
          if (result.swarm_enabled) meta.push("Swarm");
          if (result.total_time) meta.push(`${Number(result.total_time).toFixed(1)} 秒`);
          if (result.iterations) meta.push(`${result.iterations} 轮`);
          appendMessage({ role: "assistant", content: result.answer || "未返回回答", meta });
          updateStatus(result);
          loadRecent();
        }
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error(`任务超时，最后状态：${lastStatus || "未知"}`);
  };

  const sendQuestion = async (value = question.trim()) => {
    if (!value) return;
    if (!authTokenRef.current) {
      pendingAction.current = () => sendQuestion(value);
      setVerifyOpen(true);
      return;
    }
    navigate("qa", page !== "qa");
    appendMessage({ role: "user", content: value });
    setQuestion("");
    setSending(true);
    setProgress({ stage: "dispatch", label: "任务已提交，等待后端接收", percent: 3, mode: "协作", agents: [{ name: "Web API", state: "排队" }] });
    const loadingId = createMessageId();
    setMessages((items) => [...items, { id: loadingId, role: "assistant", content: "正在分析，请稍候", loading: true }]);
    try {
      const response = await fetch("/api/chat/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: value, session_id: sessionId, auth_token: authTokenRef.current }) });
      const task = await response.json();
      if (!response.ok) {
        setMessages((items) => items.filter((item) => item.id !== loadingId));
        if (task.error === "not_verified") {
          clearAuthToken();
          pendingAction.current = () => sendQuestion(value);
          setVerifyOpen(true);
          return;
        }
        appendMessage({ role: "assistant", content: task.answer || task.error || "请求失败", error: true });
        return;
      }
      await pollTask(task.task_id, loadingId);
    } catch (err) {
      setMessages((items) => items.filter((item) => item.id !== loadingId));
      appendMessage({ role: "assistant", content: `请求失败：${err instanceof Error ? err.message : String(err)}`, error: true });
    } finally {
      setSending(false);
    }
  };

  const newSession = () => {
    setSessionId(createSessionId());
    setMessages([{ id: createMessageId(), role: "assistant", content: "已开始新会话。请描述问题。" }]);
    setProgress({ stage: "dispatch", label: "等待问题输入", percent: 0, mode: "协作" });
  };

  return (
    <main className="site-shell">
      {page === "home" && <HomePage onNavigate={navigate} />}
      {page === "agents" && <InfoPage kind="agents" onNavigate={navigate} />}
      {page === "safety" && <InfoPage kind="safety" onNavigate={navigate} />}
      {page === "knowledge" && <InfoPage kind="knowledge" onNavigate={navigate} />}
      {page === "qa" && <QaPage sessionId={sessionId} progress={progress} messages={messages} recent={recent} question={question} sending={sending} onQuestionChange={setQuestion} onSubmit={() => sendQuestion()} onNewSession={newSession} onHome={() => navigate("home")} onRecent={(text) => { setQuestion(text); navigate("qa"); }} />}
      <VerifyDialog open={verifyOpen} onCancel={() => setVerifyOpen(false)} onVerified={verify} />
    </main>
  );
}
