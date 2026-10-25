import type { AssistantMessage } from "../contracts";

/** A live reload begun before Send must not erase a reply received while it was in flight. */
export function mergeThreadMessages(fetched: AssistantMessage[], current: AssistantMessage[]): AssistantMessage[] {
  const byId = new Map(fetched.map(message => [message.id, message]));
  for (const message of current) byId.set(message.id, message);
  return [...byId.values()].sort((a,b) => Date.parse(a.createdAt) - Date.parse(b.createdAt));
}
