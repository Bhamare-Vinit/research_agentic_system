import { useEffect, useState } from "react";

import { fetchHealth, fetchThread, streamResearch } from "./api.js";
import BlockRenderer from "./blocks/BlockRenderer.jsx";

const THREAD_STORAGE_KEY = "dossier.thread";

function rememberedThread() {
  try {
    return window.localStorage.getItem(THREAD_STORAGE_KEY);
  } catch {
    return null;
  }
}

function rememberThread(threadId) {
  try {
    window.localStorage.setItem(THREAD_STORAGE_KEY, threadId);
  } catch {
    return;
  }
}

function forgetThread() {
  try {
    window.localStorage.removeItem(THREAD_STORAGE_KEY);
  } catch {
    return;
  }
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [turns, setTurns] = useState([]);
  const [threadId, setThreadId] = useState(rememberedThread);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState(null);
  const [failure, setFailure] = useState(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    const remembered = rememberedThread();
    if (!remembered) return;
    fetchThread(remembered)
      .then((session) => {
        if (session && session.turns.length) setTurns(session.turns);
      })
      .catch(() => forgetThread());
  }, []);

  const running = status !== null;

  async function ask(event) {
    event.preventDefault();
    const query = draft.trim();
    if (!query || running) return;

    setDraft("");
    setFailure(null);
    setStatus("Opening the dossier");
    setTurns((current) => [...current, { query, answer: null }]);

    await streamResearch(query, threadId, (message) => {
      if (message.type === "status") {
        setStatus(message.message);
      }
      if (message.type === "error") {
        setFailure(message.message);
      }
      if (message.type === "done") {
        setThreadId(message.thread_id);
        rememberThread(message.thread_id);
        setTurns((current) =>
          current.map((turn, index) =>
            index === current.length - 1 ? { ...turn, answer: message } : turn
          )
        );
      }
    });

    setStatus(null);
  }

  return (
    <div className="shell">
      <header className="masthead">
        <h1>Dossier</h1>
        <div className="meta">
          {turns.length > 0 && (
            <button
              type="button"
              className="reset"
              onClick={() => {
                forgetThread();
                setThreadId(null);
                setTurns([]);
              }}
            >
              new session
            </button>
          )}
          {" "}
          {health
            ? `${health.model} via ${health.provider}${health.search_configured ? " · tavily" : " · no search"}${health.tracing ? ` · tracing ${health.tracing}` : ""}`
            : "backend unreachable"}
        </div>
      </header>

      {failure && <div className="failure">{failure}</div>}

      {turns.length === 0 && !running && (
        <p className="empty">Ask Dossier to research something.</p>
      )}

      {turns.map((turn, index) => (
        <article className="turn" key={index}>
          <div className="question">
            <span>you</span>
            {turn.query}
          </div>
          <div className="answer">
            {turn.answer ? (
              <BlockRenderer blocks={turn.answer.blocks} />
            ) : (
              <span className="status">{status || "working"}</span>
            )}
          </div>
        </article>
      ))}

      <div className="composer">
        <form onSubmit={ask}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Research the current state of solid-state batteries, especially cost"
            disabled={running}
          />
          <button type="submit" disabled={running || !draft.trim()}>
            {running ? "researching" : "ask"}
          </button>
        </form>
      </div>
    </div>
  );
}
