export type Page = "home" | "agents" | "safety" | "knowledge" | "qa";

export type MessageRole = "assistant" | "user";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  loading?: boolean;
  error?: boolean;
  meta?: string[];
}

export interface AgentProgress {
  stage?: "dispatch" | "retrieval" | "analysis" | "safety" | "reply";
  label?: string;
  percent?: number;
  mode?: string;
  agents?: Array<{ name?: string; state?: string }>;
}

export interface ChatResult {
  answer?: string;
  error?: string;
  session_id?: string;
  swarm_enabled?: boolean;
  total_time?: number;
  iterations?: number;
  agent_id?: string;
  agents_involved?: string[];
}

export interface ChatTask {
  task_id: string;
  status: "running" | "completed" | "failed";
  progress?: AgentProgress;
  result?: ChatResult;
  error?: string;
}

export interface RecentConversation {
  id?: string;
  title?: string;
  question?: string;
  created_at?: string;
}
