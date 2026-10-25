import type { BudgetRequestInput } from "@/lib/contracts/budget-requests";

interface Submission { input: BudgetRequestInput; status: "saving" | "unknown" }
/** Preserve an unresolved submission across route and sheet unmounts. */
export function createRequestSession() {
  let snapshot: Submission | undefined;
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach(listener => listener());
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    begin(input: BudgetRequestInput) {
      if (snapshot) return false;
      snapshot = { input: structuredClone(input), status: "saving" }; notify(); return true;
    },
    retry() {
      if (snapshot?.status !== "unknown") return undefined;
      snapshot = { ...snapshot, status: "saving" }; notify(); return snapshot.input;
    },
    unknown(id: string) {
      if (snapshot?.input.clientRequestId !== id) return;
      snapshot = { ...snapshot, status: "unknown" }; notify();
    },
    resolve(id: string) {
      if (snapshot?.input.clientRequestId !== id) return;
      snapshot = undefined; notify();
    },
  };
}
export const requestSubmission = createRequestSession();
