"""Northstar's Factory Droid integration (runtime, not codegen).

- `sdk_runner.SdkDroidRunner`: the real Droid SDK runner (lazy SDK import; used only when
  DROID_RUNNER=sdk and FACTORY_API_KEY is set).
- `sdk_tools`: the backend's scoped toolbox exposed to Droid as in-process MCP tools.
- `tool_manifest.json`: generated tool names, descriptions and input schemas (read + draft only).
- `prompts/`: system and task prompts.

The DroidRunner interface, toolbox and deterministic FakeDroidRunner live in `backend/app/agent/`.
Importing this package never imports the SDK.
"""
