import type { Dataset } from "@/fixtures";
import type { AllocationState, BudgetRequest, ForecastBundle, ForecastEvidence, WeeklyHistoryResponse } from "@/lib/contracts";
import type { DataClient } from "./client";
import { adaptAllocationState, adaptBudgetRequest, type AllocationStateWire, type BudgetRequestWire } from "./budget-requests";
import { hydrateForecastDashboard } from "./forecast-dashboard";
import { adaptWeeklyHistory, type WeeklyHistoryWireResponse } from "./weekly-history";
import { MockDataClient } from "./mock-client";
import { makeSnapshotReply } from "./snapshot-reply";

export interface DemoSnapshot {
  dataset: Dataset;
  bundle: ForecastBundle;
  weeklyHistory: WeeklyHistoryResponse[];
  evidence: { items: ForecastEvidence[] };
  requests: BudgetRequest[];
  allocationState: AllocationState;
  asOf: string;
}

/** An explicit public build flag selects saved data; local API configuration stays untouched. */
export function demoSnapshotPath(): string | undefined {
  const path = process.env.NEXT_PUBLIC_DEMO_SNAPSHOT;
  return path?.trim() || undefined;
}

const snapshots = new Map<string, Promise<DemoSnapshot>>();

export async function readDemoSnapshot(base: string, fetcher: typeof fetch = fetch): Promise<DemoSnapshot> {
  if (!/^\/[a-zA-Z0-9/_-]+$/.test(base)) throw new Error("The demo snapshot path is invalid.");
  const root = base.replace(/\/$/, "");
  async function read<T>(name: string): Promise<T> {
    const response = await fetcher(`${root}/${name}.json`, { cache: "force-cache" });
    if (!response.ok) throw new Error(`The saved demo could not load ${name}. Please retry.`);
    return response.json();
  }
  const [manifest, company, teams, people, spending, budgets, forecasts, context, documents, proposals, decisions, wireBundle, evidence, wireWeekly, wireRequests, wireAllocation] = await Promise.all([
    read<{ schemaVersion: number; asOf: string }>("manifest"),
    read<Dataset["company"]>("company"), read<Dataset["teams"]>("teams"), read<Dataset["people"]>("people"),
    read<Dataset["spending"]>("spending"), read<Dataset["budgets"]>("budgets"), read<Dataset["forecasts"]>("forecasts"),
    read<Dataset["context"]>("context"), read<Dataset["documents"]>("documents"),
    read<Dataset["proposals"]>("proposals"), read<Dataset["decisions"]>("decisions"),
    read<unknown>("forecast-views"), read<{ items: ForecastEvidence[] }>("forecast-evidence"),
    read<WeeklyHistoryWireResponse[]>("weekly-history"), read<{ items: BudgetRequestWire[] }>("budget-requests"),
    read<AllocationStateWire>("allocation-state"),
  ]);
  if (manifest.schemaVersion !== 1 || !Number.isFinite(Date.parse(manifest.asOf)) || !company?.currentPeriod) throw new Error("The saved demo has an unsupported format.");
  const bundle = hydrateForecastDashboard(wireBundle);
  const allocationState = adaptAllocationState(wireAllocation);
  const { start, end } = company.currentPeriod;
  const data: Omit<Dataset, "scriptedReply"> = {
    company: { ...company, isDemo: true }, teams, people, spending,
    budgets: budgets.filter(budget => budget.period.start === start && budget.period.end === end && budget.unit === company.budgetUnit),
    forecasts, context, documents, proposals, decisions, threads: {},
  };
  if (!data.budgets.length || !bundle.views.some(view => view.scope.type === "company" && view.scope.id === company.id)) throw new Error("The saved demo is missing its company planning data.");
  return {
    dataset: { ...data, scriptedReply: makeSnapshotReply(data, bundle, { envelopeTotal: Number(allocationState.envelopeTotal) }) },
    bundle, weeklyHistory: wireWeekly.map(history => adaptWeeklyHistory(history)), evidence,
    requests: wireRequests.items.map(adaptBudgetRequest), allocationState, asOf: manifest.asOf,
  };
}

/** Share immutable downloaded assets; each client below owns an independent mutable session. */
export function loadDemoSnapshot(): Promise<DemoSnapshot> {
  const base = demoSnapshotPath() ?? "/demo";
  let pending = snapshots.get(base);
  if (!pending) {
    pending = readDemoSnapshot(base).catch(error => { snapshots.delete(base); throw error; });
    snapshots.set(base, pending);
  }
  return pending;
}

export function createSnapshotDataClient(load: () => Promise<DemoSnapshot> = loadDemoSnapshot): DataClient {
  let pending: Promise<MockDataClient> | undefined;
  const methods = new Map<PropertyKey, unknown>();
  return new Proxy({} as DataClient, {
    get(_target, key) {
      if (typeof key !== "string" || key === "then" || !Object.prototype.hasOwnProperty.call(MockDataClient.prototype, key) || key === "constructor") return undefined;
      if (!methods.has(key)) methods.set(key, async (...args: unknown[]) => {
        pending ??= load().then(snapshot => new MockDataClient(snapshot.dataset, snapshot)).catch(error => { pending = undefined; throw error; });
        const client = await pending;
        const method = (client as unknown as Record<string, (...values: unknown[]) => unknown>)[key];
        return method.apply(client, args);
      });
      return methods.get(key);
    },
  });
}
