import { useEffect, useState } from "react";

import { fetchHealth, fetchThread, streamResearch } from "./api.js";
import BlockRenderer from "./blocks/BlockRenderer.jsx";
import ProgressBlock from "./blocks/ProgressBlock.jsx";

const THREAD_STORAGE_KEY = "dossier.thread";
const SUGGESTIONS = [
  "Research the current state of solid-state batteries, especially cost",
  "What did we find on hybrid search benchmarks?",
  "How does the JEV model work?",
];

function TurnMeta({ answer }) {
  const retrieval = answer.retrieval_stats || {};
  const llm = answer.llm || {};
  const parts = [];

  if (retrieval.whole_dossier_tokens) {
    parts.push(
      `retrieved ${retrieval.retrieved_tokens} of ${retrieval.whole_dossier_tokens} dossier tokens (${retrieval.tokens_saved_pct}% saved)`
    );
  }
  if (llm.total_tokens) {
    parts.push(`${llm.prompt_tokens} in / ${llm.completion_tokens} out model tokens`);
  }
  parts.push(
    answer.iterations === 1 ? "1 research pass" : `${answer.iterations} research passes`
  );
  if (answer.dropped_finding_ids?.length) {
    parts.push(`${answer.dropped_finding_ids.length} invented id dropped`);
  }

  return <div className="turn-meta">{parts.join(" · ")}</div>;
}

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
  const [steps, setSteps] = useState([]);
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
    setStatus("Opening the case file");
    setSteps([]);
    setTurns((current) => [...current, { query, answer: null }]);

    await streamResearch(query, threadId, (message) => {
      if (message.type === "status") {
        setStatus(message.message);
      }
      if (message.type === "step") {
        setSteps((current) => [...current, message]);
      }
      if (message.type === "decision" && message.decision === "research") {
        setStatus("Researching: " + message.reason);
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
    setSteps([]);
  }

  function startNewSession() {
    forgetThread();
    setThreadId(null);
    setTurns([]);
  }

  return (
    <div className="app">
      <header className="titlebar">
        <div className="brand">
          <div className="logo">D</div>
          <div>
            <h1>Dossier</h1>
            <p>Autonomous research agent</p>
          </div>
        </div>
        <div className="titlebar-actions">
          <span className={health ? "health online" : "health offline"}>
            <span className="dot" />
            {health
              ? `${health.model}${health.search_configured ? " · tavily" : " · no search"}`
              : "backend unreachable"}
          </span>
          {turns.length > 0 && (
            <button type="button" className="ghost" onClick={startNewSession} disabled={running}>
              New session
            </button>
          )}
        </div>
      </header>

      <main className="thread">
        {failure && <div className="failure">{failure}</div>}

        {turns.length === 0 && !running && (
          <div className="empty">
            <h2>What should we look into?</h2>
            <p>Dossier plans its own web research and keeps every finding, with its source, in a case file.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => setDraft(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, index) => (
          <article className="turn" key={index}>
            <div className="question">
              <div className="bubble">{turn.query}</div>
            </div>
            <div className="answer">
              <div className="avatar">D</div>
              <div className="card">
                {turn.answer ? (
                  <BlockRenderer
                    blocks={turn.answer.blocks}
                    fallbackText={turn.answer.final_answer}
                    footer={<TurnMeta answer={turn.answer} />}
                  />
                ) : (
                  <ProgressBlock status={status || "working"} steps={steps} />
                )}
              </div>
            </div>
          </article>
        ))}
      </main>

      <footer className="composer">
        <form onSubmit={ask}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask a question or start new research"
            disabled={running}
          />
          <button type="submit" disabled={running || !draft.trim()}>
            {running ? "Working" : "Send"}
          </button>
        </form>
      </footer>
    </div>
  );
}
