/** Kept outside route components so an uncertain write cannot be lost by closing or navigating. */
export interface AllocationOperation {
  id: string;
  kind: "message" | "targets" | "request";
  request: unknown;
  status: "preparing" | "unknown" | "prepared" | "failed";
  clientMessageId?: string;
  proposalId?: string;
  matches?: boolean;
  reason?: string;
  error?: string;
}
export function createAllocationSession() {
  let snapshot: { operation?: AllocationOperation } = {};
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach(listener => listener());
  const pending = () => snapshot.operation?.status === "preparing" || snapshot.operation?.status === "unknown";
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    begin(operation: AllocationOperation, blockedByDecision = false) {
      if (pending() || blockedByDecision) return false;
      snapshot = { operation }; notify(); return true;
    },
    update(id: string, patch: Partial<AllocationOperation>) {
      if (snapshot.operation?.id !== id) return false;
      snapshot = { operation: { ...snapshot.operation, ...patch, id } }; notify(); return true;
    },
    clear(blockedByDecision = false) {
      if (pending() || blockedByDecision) return false;
      snapshot = {}; notify(); return true;
    },
  };
}
export const allocationSession = createAllocationSession();
