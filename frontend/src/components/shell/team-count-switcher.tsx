"use client";
import { useEffect, useState } from "react";
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

/** Demo-only: switches the mock dataset via ?teams=N and reloads so the data client re-selects it. */
export function TeamCountSwitcher() {
  const [value, setValue] = useState("default");
  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search).get("teams");
      const stored = window.localStorage.getItem("aisp.teams");
      const v: string = q === "default" ? "default" : (q ?? stored ?? "default");
      setValue(OPTIONS.some((o) => o.value === v) ? v : "default");
    } catch { /* ignore */ }
  }, []);
  return (
    <Select value={value} onValueChange={(v) => { if (!v) return; setValue(v); window.location.assign(`/?teams=${v}`); }}>
      <SelectTrigger size="sm" className="w-[190px] text-xs" aria-label="Demo dataset">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {OPTIONS.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
