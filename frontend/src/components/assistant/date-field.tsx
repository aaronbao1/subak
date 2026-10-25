"use client";
import { useId, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { resolvePlanningDate } from "@/lib/planning-drafts";

/** Native calendar retains keyboard date entry; prose resolves to an explicit date before preview. */
export function DateField({ label, value, onChange, min, optional = false }: { label: string; value?: string; onChange: (date: string) => void; min?: string; optional?: boolean }) {
  const id = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string>();
  function resolve() {
    try { onChange(resolvePlanningDate(text, value)); setError(undefined); setText(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Enter a concrete date."); }
  }
  return <div className="space-y-1.5">
    <label htmlFor={id} className="text-xs font-medium">{label}{optional ? " (optional)" : ""}</label>
    <Input id={id} type="date" value={value ?? ""} min={min} onChange={e => { onChange(e.target.value); setError(undefined); }} className="h-9 text-sm" />
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer py-1">Enter a date in words</summary>
      <div className="mt-1 flex gap-2"><Input aria-label={`${label} in words`} placeholder="November 10, 2026" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); resolve(); } }} className="h-8 text-xs" /><Button type="button" variant="outline" size="sm" onClick={resolve}>Use date</Button></div>
      <p className="mt-1">Include the year, or enter “two weeks later” to revise the current date.</p>
    </details>
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
  </div>;
}
