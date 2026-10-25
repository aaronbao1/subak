import type { DataClient } from "./client";
import { MockDataClient } from "./mock-client";
import { HttpDataClient } from "./http-client";
import { createSnapshotDataClient, demoSnapshotPath } from "./demo-snapshot";

let client: DataClient | undefined;

/**
 * Single entry point. Mock by default; set NEXT_PUBLIC_API_URL (e.g. http://localhost:8000)
 * to talk to the real backend. The endpoint contract is in docs/frontend-integration.md.
 */
export function getDataClient(): DataClient {
  if (!client) {
    const base = process.env.NEXT_PUBLIC_API_URL;
    client = demoSnapshotPath() ? createSnapshotDataClient() : base ? new HttpDataClient(base.replace(/\/$/, "")) : new MockDataClient();
  }
  return client;
}

export type { DataClient, SpendingFilter } from "./client";
