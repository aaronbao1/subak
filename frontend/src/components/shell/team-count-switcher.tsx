"use client";
import { useSyncExternalStore } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const OPTIONS = [
  { value: "default", label: "Plan example (3 teams)" },
  { value: "0", label: "0 teams" },
  { value: "1", label: "1 team" },
  { value: "4", label: "4 teams" },
  { value: "8", label: "8 teams" },
  { value: "12", label: "12 teams" },
  { value: "16", label: "16 teams" },
];

function readCurrent(): string {
  try {
    const q = new URLSearchParams(window.location.search).get("teams");
    const stored = window.localStorage.getItem("aisp.teams");
    const v = q === "default" ? "default" : (q ?? stored ?? "default");
    return OPTIONS.some((o) => o.value === v) ? v : "default";
  } catch {
    return "default";
  }
}
const noop = () => () => {};

/** Demo-only: switches the mock dataset via ?teams=N and hard-reloads so the data client re-selects it. */
export function TeamCountSwitcher() {
  const value = useSyncExternalStore(noop, readCurrent, () => "default");
  return (
    <Select
      items={OPTIONS}
      value={value}
      onValueChange={(v) => {
        if (!v) return;
        // Full reload on purpose: the mock DataClient is a module singleton that reads ?teams= on construction.
        const url = new URL(window.location.origin + "/");
        url.searchParams.set("teams", v);
        window.location.href = url.toString();
      }}
    >
      <SelectTrigger size="sm" className="w-[190px] text-xs" aria-label="Demo dataset">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {OPTIONS.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
