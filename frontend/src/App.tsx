
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUp,
  Check,
  ChevronDown,
  CircleHelp,
  Command,
  Copy,
  Menu,
  MessageSquare,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

type Metadata = {
  resolution_source: "LIVE_INFERENCE" | "LLM_CACHE";
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  metadata?: Metadata;
  id: string;
};

// Production uses Render. Local development uses localhost.
const API_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV
    ? "http://localhost:8000"
    : "https://lyftr-ai-fullstack-e46s.onrender.com")
).replace(/\/$/, "");

const makeSession = () => `s-${crypto.randomUUID().slice(0, 8)}`;

export default function App() {
  const [sessionId, setSessionId] = useState(makeSession);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(
    "You are Lyftr AI, a helpful, accurate, and concise assistant."
  );
  const [showSettings, setShowSettings] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<"checking" | "online" | "offline">(
    "checking"
  );
  const [copied, setCopied] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_URL}/health`);
        if (!response.ok) throw new Error("Backend unavailable");
        await response.json();
        setHealth("online");
      } catch {
        setHealth("offline");
      }
    };

    void checkHealth();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const newChat = () => {
    setSessionId(makeSession());
    setMessages([]);
    setError("");
    setInput("");
  };

  async function sendMessage(e?: FormEvent) {
    e?.preventDefault();

    const message = input.trim();
    if (!message || sending) return;

    setError("");
    setInput("");
    setSending(true);

    const userMessage: Message = {
      role: "user",
      content: message,
      id: crypto.randomUUID(),
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          system_prompt: systemPrompt,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Something went wrong. Please try again.");
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.reply,
          metadata: data.metadata,
          id: crypto.randomUUID(),
        },
      ]);

      setHealth("online");
    } catch (err) {
      const messageText =
        err instanceof Error ? err.message : "Unable to reach the server.";

      setError(messageText);
      setHealth("offline");
    } finally {
      setSending(false);
    }
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  const copyText = async (id: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(id);
      window.setTimeout(() => setCopied(""), 1300);
    } catch {
      setError("Unable to copy text.");
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={19} />
          </div>
          <span>
            lyftr<span className="brand-ai">.ai</span>
          </span>
        </div>

        <button className="new-chat" onClick={newChat}>
          <Plus size={16} /> New conversation <span>⌘ K</span>
        </button>

        <div className="side-label">WORKSPACE</div>
        <div className="side-item active">
          <MessageSquare size={16} /> AI Assistant
        </div>

        <div className="side-item">
          <Activity size={16} /> System status
          <span className={`status-dot ${health}`} />
        </div>

        <div className="sidebar-bottom">
          <div className="secure-card">
            <ShieldCheck size={17} />
            <div>
              <b>Private by design</b>
              <small>Your chats stay in your session.</small>
            </div>
          </div>

          <div className="profile">
            <div className="avatar">L</div>
            <div>
              <b>Lyftr Workspace</b>
              <small>Personal plan</small>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="crumb">
            <span>Workspace</span>
            <span className="slash">/</span>
            <b>AI Assistant</b>
            <span className="beta">BETA</span>
          </div>

          <div className="top-actions">
            <div className={`connection ${health}`}>
              <span />
              {health === "online"
                ? "API connected"
                : health === "offline"
                  ? "API disconnected"
                  : "Connecting"}
            </div>

            <button
              className="icon-button"
              title="System prompt settings"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Command size={17} />
            </button>

            <button className="icon-button mobile-menu" title="Menu">
              <Menu size={18} />
            </button>
          </div>
        </header>

        {showSettings && (
          <section className="settings-panel">
            <div>
              <b>System prompt</b>
              <p>Customize the assistant's behavior for this conversation.</p>
            </div>

            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={3}
            />

            <button
              className="small-primary"
              onClick={() => setShowSettings(false)}
            >
              Save prompt
            </button>
          </section>
        )}

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">
                <Sparkles size={25} />
              </div>

              <div className="eyebrow">
                <span /> YOUR AI WORKSPACE
              </div>

              <h1>
                Ideas start here.
                <br />
                <span>Let's make them happen.</span>
              </h1>

              <p className="welcome-copy">
                Ask anything. Explore ideas, solve problems, and get things
                done with your AI assistant.
              </p>

              <div className="suggestions">
                {[
                  [
                    "✦",
                    "Explain a complex topic",
                    "Explain how large language models work in simple terms.",
                  ],
                  [
                    "⌘",
                    "Help me write",
                    "Write a concise professional email asking for a project update.",
                  ],
                  [
                    "↗",
                    "Think through an idea",
                    "Help me brainstorm a useful AI-powered product idea.",
                  ],
                ].map(([icon, title, prompt]) => (
                  <button
                    className="suggestion"
                    key={title}
                    onClick={() => setInput(prompt)}
                  >
                    <span className="suggestion-icon">{icon}</span>
                    <span>
                      <b>{title}</b>
                      <small>{prompt}</small>
                    </span>
                    <ArrowUp size={15} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              <div className="conversation-heading">
                <div>
                  <span className="eyebrow">CONVERSATION</span>
                  <h2>AI Assistant</h2>
                </div>

                <button className="text-button" onClick={newChat}>
                  <Plus size={14} /> New chat
                </button>
              </div>

              {messages.map((m) => (
                <div className={`message-row ${m.role}`} key={m.id}>
                  <div className={`message-avatar ${m.role}`}>
                    {m.role === "assistant" ? <Sparkles size={16} /> : "S"}
                  </div>

                  <div className="message-content">
                    <div className="message-name">
                      {m.role === "assistant" ? "Lyftr AI" : "You"}
                      <span>{m.role === "assistant" ? "· Just now" : ""}</span>
                    </div>

                    {m.role === "assistant" ? (
                      <div
                        className="assistant-card"
                        data-testid="assistant-message"
                      >
                        <div className="reply-text">{m.content}</div>

                        {m.metadata && (
                          <div className="metadata">
                            <span
                              className={`source ${
                                m.metadata.resolution_source === "LLM_CACHE"
                                  ? "cached"
                                  : ""
                              }`}
                              data-testid="meta-source"
                            >
                              <i /> {m.metadata.resolution_source}
                            </span>

                            <span data-testid="meta-model">
                              <b>Model</b> {m.metadata.model}
                            </span>

                            <span data-testid="meta-latency">
                              <b>Latency</b> {m.metadata.latency_ms} ms
                            </span>

                            <span data-testid="meta-input-tokens">
                              <b>In</b> {m.metadata.input_tokens}
                            </span>

                            <span data-testid="meta-output-tokens">
                              <b>Out</b> {m.metadata.output_tokens}
                            </span>

                            {m.metadata.key_id && (
                              <span>
                                <b>Key</b> {m.metadata.key_id}
                              </span>
                            )}

                            {m.metadata.fallback_attempts > 0 && (
                              <span className="fallback">
                                <Zap size={11} />{" "}
                                {m.metadata.fallback_attempts} fallback(s)
                              </span>
                            )}
                          </div>
                        )}

                        <button
                          className="copy-button"
                          onClick={() => void copyText(m.id, m.content)}
                        >
                          {copied === m.id ? (
                            <Check size={13} />
                          ) : (
                            <Copy size={13} />
                          )}
                          {copied === m.id ? "Copied" : "Copy"}
                        </button>
                      </div>
                    ) : (
                      <div className="user-bubble">{m.content}</div>
                    )}
                  </div>
                </div>
              ))}

              {sending && (
                <div className="message-row assistant">
                  <div className="message-avatar assistant">
                    <Sparkles size={16} />
                  </div>
                  <div className="typing">
                    <span />
                    <span />
                    <span />
                    <small>Lyftr is thinking</small>
                  </div>
                </div>
              )}

              {error && (
                <div className="error-banner">
                  <CircleHelp size={16} />
                  <span>{error}</span>
                  <button onClick={() => setError("")}>Dismiss</button>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </section>

        <footer className="composer-wrap">
          {messages.length === 0 && (
            <div className="composer-hint">
              <ShieldCheck size={13} /> AI can make mistakes. Verify important
              information.
            </div>
          )}

          {error && messages.length === 0 && (
            <div className="error-banner">
              <CircleHelp size={16} />
              <span>{error}</span>
              <button onClick={() => setError("")}>Dismiss</button>
            </div>
          )}

          <form className="composer" onSubmit={sendMessage}>
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Message Lyftr AI..."
              rows={1}
              disabled={sending}
            />

            <div className="composer-bottom">
              <span>
                <kbd>↵</kbd> to send <span className="hint-divider">·</span>{" "}
                <kbd>shift + ↵</kbd> for new line
              </span>

              <button
                data-testid="send-button"
                className="send-button"
                type="submit"
                disabled={!input.trim() || sending}
                aria-label="Send message"
              >
                {sending ? (
                  <RotateCcw size={16} className="spin" />
                ) : (
                  <ArrowUp size={18} />
                )}
              </button>
            </div>
          </form>

          <div className="footer-note">
            Powered by resilient AI infrastructure <span>·</span> Built with
            care by Lyftr
          </div>
        </footer>
      </main>
    </div>
  );
}
