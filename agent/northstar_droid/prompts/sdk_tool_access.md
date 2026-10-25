How to reach the northstar tools in this session:

- The tools are the MCP tools {tool_ids}. They are deferred: load them first with one Script that runs
  `text(await tools.ToolSearch({{query: "select:{tool_ids_csv}"}}))`.
- Then call them from a Script as `await tools.northstar.<tool>({{...}})`, for example
  `text(await tools.northstar.search_corpus({{query: ""}}))`. Pass arguments as one object whose keys
  are the tool's parameter names. Results are JSON text; `JSON.parse` them when you need fields.
- Scripts may use only `tools.ToolSearch`, `tools.northstar.<tool>`, `text(...)`, `JSON` and plain
  JavaScript (variables, loops, string and array methods). A Script whose CODE touches anything else
  (other tools, `fetch`, `import`, `require`, `eval`, `Function`, `process`, `globalThis`, `this`,
  prototype or constructor access, `\u`/`\x` escapes outside strings, regular-expression literals,
  computed access such as `obj[key]`) is refused by the backend before it runs, and the whole run
  usually ends there. Text inside strings is fine: rationales and quotes may use any words, and may
  cite `research-eval-plan`.
- Rules that avoid refusals:
  - Look items up with `list.find((a) => a.team === "research")` or a `for (const a of list)` loop,
    never `byTeam[team]`. Fixed keys are fine: `r.items`, `r["items"]`, `r.items[0]`.
  - Use string methods (`split`, `includes`, `startsWith`, `replaceAll(",", "")`), never `/regex/`.
  - Do not name variables `top`, `self`, `parent`, `global`, `window`, `document`, `location`,
    `frames`, `opener`, `navigator` or `class`; use names such as `topTeam`, `doc` or `periods`.
  - Do not start a statement with `[` right after a closing `}}`; assign the array first
    (`const teams = ["research", "product"]; teams.forEach(...)`).
  - Long or multi-line text (a rationale, a quote) can go in an input block before the program:
    `// @input: rationale <<'EOF'` ... `EOF`, then read it as `inputs.rationale`.
  - Do the arithmetic in one Script, then call `draft_proposal` with the finished numbers.
- A refused call returns `{{"error": {{"code", "message", "details"}}}}`. For `invalid_arguments`, fix the
  arguments named in `details.errors` and call again once instead of giving up.
- There is no shell, no file access and no network. Do not ask the user questions; this run is
  non-interactive.
