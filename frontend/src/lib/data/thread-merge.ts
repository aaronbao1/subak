import type { AssistantMessage } from "../contracts";

/** Server snapshots have sequence order; send receipts contain only the newly accepted pair. */
export function mergeThreadMessages(fetched: AssistantMessage[], current: AssistantMessage[], source: "snapshot" | "append" = "snapshot"): AssistantMessage[] {
  const key = (message: AssistantMessage) => message.role === "user" && message.clientMessageId ? `request:${message.clientMessageId}` : message.id;
  const byId = new Map(fetched.map(message => [key(message), message]));
  for (const message of current) {
    if (message.id.startsWith("pending:") && byId.has(key(message))) continue;
    byId.set(key(message), message);
  }
  // Timestamps can tie (a frozen demo clock) or differ from the local optimistic clock.
  // Both inputs already have conversation order, so retain that order instead of sorting by time.
  if (source === "snapshot") return [...byId.values()];

  const order = [...new Set(current.map(key))];
  const incoming = fetched.map(key);
  let previous: string | undefined;
  incoming.forEach((id, index) => {
    if (!order.includes(id)) {
      const previousIndex = previous ? order.indexOf(previous) : -1;
      const next = incoming.slice(index + 1).find(candidate => order.includes(candidate));
      // An accepted user echo anchors a recovered reply beside the original request,
      // even when the user has already sent another message after its timeout.
      const insertion = previousIndex >= 0 ? previousIndex + 1 : next ? order.indexOf(next) : order.length;
      order.splice(insertion, 0, id);
    }
    previous = id;
  });
  return order.map(id => byId.get(id)!);
}
