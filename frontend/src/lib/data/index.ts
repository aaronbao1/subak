import type { DataClient } from "./client";
import { MockDataClient } from "./mock-client";

let client: DataClient | undefined;

/** Single entry point. Swap to an HttpDataClient by env var once the backend exists. */
export function getDataClient(): DataClient {
  if (!client) client = new MockDataClient();
  return client;
}

export type { DataClient, SpendingFilter } from "./client";
