const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

export async function fetchHealth() {
  const response = await fetch(`${BASE_URL}/health/`);
  return response.json();
}

export async function fetchDossier() {
  const response = await fetch(`${BASE_URL}/dossier/`);
  return response.json();
}

export async function streamResearch(query, threadId, onEvent) {
  const response = await fetch(`${BASE_URL}/research/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id: threadId }),
  });

  if (!response.ok) {
    const problem = await response.json().catch(() => ({ error: response.statusText }));
    onEvent({ type: "error", message: problem.error || "request failed" });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop();

    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        onEvent({ type: "error", message: "could not parse a stream event" });
      }
    }
  }
}
