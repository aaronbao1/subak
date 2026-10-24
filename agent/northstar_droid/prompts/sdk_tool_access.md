How to reach the northstar tools in this session:

- The tools are the MCP tools {tool_ids}. They are deferred: load them first with one Script that runs
  `text(await tools.ToolSearch({{query: "select:{tool_ids_csv}"}}))`.
- Then call them from a Script as `await tools.northstar.<tool>({{...}})`, for example
  `text(await tools.northstar.search_corpus({{query: ""}}))`. Pass arguments as one object whose keys
  are the tool's parameter names. Results are JSON text; `JSON.parse` them when you need fields.
- Scripts may use only `tools.ToolSearch`, `tools.northstar.<tool>`, `text(...)`, `JSON` and plain
  JavaScript (variables, loops, string and array methods). A Script that touches anything else
  (other tools, `fetch`, `import`, `require`, `eval`, `Function`, `process`, `globalThis`, `this`,
  prototype or constructor access, `\u`/`\x` escapes, regular-expression literals, computed access
  such as `obj[key]`) is refused by the backend before it runs. Use fixed property names (`r.items`,
  `r["items"]`, `r.items[0]`) and `for (const x of list)` loops.
- A refused call returns `{{"error": {{"code", "message", "details"}}}}`. For `invalid_arguments`, fix the
  arguments named in `details.errors` and call again once instead of giving up.
- There is no shell, no file access and no network. Do not ask the user questions; this run is
  non-interactive.
