# Interactive Subak demo

The published demo serves the complete generated company dataset and saved numerical forecast publications as static assets. It does not require a hosted Python service, a persistent database, or a Factory API key.

Visitors can explore weekly actuals versus issued forecasts, inspect teams and source documents, submit a team update, and review or apply internal allocation proposals. Each visitor works on an independent in-memory copy. Reloading starts a fresh session; no visitor changes alter the source company records or another visitor’s experience. Assistant responses use the snapshot and the available planning actions; the public demo does not make live Factory calls.

## Build and run

From `frontend/`:

```sh
NEXT_PUBLIC_DEMO_SNAPSHOT=/demo npm run build
npm run start -- --hostname 127.0.0.1 --port 3001
```

Vercel builds select `/demo` by default. Explicit `NEXT_PUBLIC_DEMO_SNAPSHOT` configuration can override the asset root. Local development can continue using the full backend by leaving that selector unset and setting `NEXT_PUBLIC_API_URL` in the ignored frontend environment file. Never include a Factory key in a frontend environment variable.

Both `/` and `/overview` are part of the same deployment. The full backend and live SDK remain available separately; see [local preview setup](subak-local-preview.md).
