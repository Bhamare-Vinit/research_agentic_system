import { useEffect, useState } from "react";

import { fetchHealth, streamResearch } from "./api.js";
import BlockRenderer from "./blocks/BlockRenderer.jsx";

export default function App() {
  const [health, setHealth] = useState(null);
  const [turns, setTurns] = useState([]);
  const [threadId, setThreadId] = useState(null);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState(null);
  const [failure, setFailure] = useState(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
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
