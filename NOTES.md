# Notes

## Planning loop and stopping

- The Main Agent first calls `check_memory`, which lists topics and categories only. It then
  retrieves the categories the question needs.
- If those findings are enough, it answers. If not, it calls `research` with a plan: the
  categories to cover and what to find in each.
- The graph routes to the Research Agent. That agent works in rounds (search, fetch, file) and
  calls `report` once the question is answered.
- Control returns to the Main Agent, which re-reads the case file and decides again: another
  pass, or answer.
- Stopping is the agents' own call. The caps are safety nets only: 5 research passes, 12 Research
  Agent steps, 8 Main Agent steps.

## Dossier and retrieval

- `dossier.json` is organised as topic → category → findings. Each finding has an `id`, `claim`,
  `source` URL, `date` and `last_verified`.
- A write is rejected for a non-URL source, a generic category (`overview`, `info`, …), or an
  exact duplicate.
- The model picks the slice: `retrieve(topic, category)` returns one category, capped at
  `RETRIEVAL_TOP_K`. It never receives the whole file.
- Answers cite finding ids. Python fills in the real claim and URL from what was retrieved, and
  drops any id it cannot match, so sources cannot be invented.

## Contradictions

- Nothing is overwritten. A conflicting figure is filed alongside the old one, with its own date.
- At answer time, the later date wins. The agent explains the change and shows both findings in
  an `update` block.
- There is no stored link between the old and new findings. `supersedes` exists but is unused.

## Hardest, and still fuzzy

- **Categorisation.** Early runs dumped everything into `overview`, so retrieval failed. The fix
  was a research plan plus rejected category names.
- **Subject drift.** "jev model" was once researched as Jevons Paradox. The agent must now
  confirm the subject, or report that it could not.
- **Luna.** It needs the Responses API for tool calls.
- **Fuzzy:** the false-memory refusal is prompt-driven, not enforced in code.

## Not reached

- **Researching sub-questions in parallel.**
- **An explicit `supersedes` link** between old and new findings.

## Choices

- **Model:** `gpt-5.6-luna`, with an OpenRouter fallback (`gpt-4o-mini`).
- **Search:** Tavily, for its free tier and LLM-ready snippets.
- **MCP:** web tools go through the MCP server; case-file tools stay in-process.
- **Tool schemas:** every tool uses a strict Pydantic schema.

## AI usage

- I used Claude Code and github copilot as a pair programmer for scaffolding, prompts, debugging and live test runs.
- I set the design and reviewed every change before committing it.
- I corrected its mistakes when they came up, for example over-retrieval and ids leaking into
  replies.
