import type { ForecastBundle, ForecastDriver } from "@/lib/contracts/forecast-view";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function owns(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

/** Restore the opt-in wire format before any forecast consumer sees it. */
export function hydrateForecastDashboard(payload: unknown): ForecastBundle {
  if (!isRecord(payload)) throw new Error("Invalid forecast response.");
  // Older servers and the full native endpoint continue to return the original contract.
  if (!owns(payload, "transport")) return payload as ForecastBundle;
  if (payload.transport !== "forecast-dashboard-v1") throw new Error("Unsupported forecast transport.");
  const pool = payload.driver_pool;
  if (!isRecord(pool) || !Array.isArray(payload.views)) throw new Error("Invalid compact forecast response.");

  function restoreReferences(refs: unknown): ForecastDriver[] | null {
    if (refs === null) return null;
    if (!Array.isArray(refs)) throw new Error("Invalid forecast driver references.");
    return refs.map((ref) => {
      if (typeof ref !== "string" || !owns(pool as Record<string, unknown>, ref)) {
        throw new Error("Missing forecast driver reference.");
      }
      const driver = (pool as Record<string, unknown>)[ref];
      if (!isRecord(driver) || typeof driver.id !== "string") throw new Error("Invalid forecast driver.");
      // Scenario editors can change a driver. Preserve JSON response isolation for
      // every occurrence, including duplicates and references in different views.
      return structuredClone(driver) as ForecastDriver;
    });
  }

  const views = payload.views.map((original) => {
    if (!isRecord(original)) throw new Error("Invalid forecast view.");
    const view = { ...original };
    for (const [refs, field] of [["included_driver_refs", "included_drivers"], ["queued_change_refs", "queued_changes"]]) {
      if (owns(view, field)) throw new Error("Ambiguous compact forecast driver representation.");
      if (owns(view, refs)) {
        view[field] = restoreReferences(view[refs]);
        delete view[refs];
      }
    }
    return view;
  });
  const bundle: Record<string, unknown> = { ...payload, views };
  delete bundle.transport;
  delete bundle.driver_pool;
  return bundle as ForecastBundle;
}
