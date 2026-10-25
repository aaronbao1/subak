"use client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ForecastBundle, ForecastView } from "@/lib/contracts";
import { scenarioComparison } from "@/lib/planning-drafts";

const number = (value: number, unit: string) => new Intl.NumberFormat("en-US", unit.toLowerCase() === "usd" ? { style: "currency", currency: "USD", maximumFractionDigits: 2 } : { maximumFractionDigits: 2 }).format(value) + (unit.toLowerCase() === "usd" ? "" : ` ${unit}`);
export function ScenarioPreview({ baseline, scenario }: { baseline: ForecastView; scenario: ForecastBundle }) {
  let comparison: ReturnType<typeof scenarioComparison>;
  try { comparison = scenarioComparison(baseline, scenario); }
  catch (e) { return <p role="alert" className="text-xs text-destructive">{e instanceof Error ? e.message : "Scenario comparison unavailable."}</p>; }
  const view = comparison.view;
  const targetMatches = view?.target.unit === baseline.target.unit && view?.target.quantity === baseline.target.quantity && view?.target.basis === baseline.target.basis;
  const chart = targetMatches ? baseline.daily.flatMap(point => {
    const date = point.date ?? point.start;
    const after = view?.daily.find(p => (p.date ?? p.start) === date && p.end === point.end);
    return after && typeof point.base === "number" && typeof after.base === "number" ? [{ date, baseline: point.base, scenario: after.base }] : [];
  }) : [];
  const range = view?.quarter_outlook;
  return <section aria-label="Scenario comparison" className="space-y-3 border-t border-border pt-4">
    <div><p className="text-xs font-medium">Hypothetical preview</p><p className="mt-1 text-xs text-muted-foreground">{baseline.scope.name ?? baseline.scope.type} · {String(baseline.quarter_outlook?.start ?? "")} to {String(baseline.quarter_outlook?.end ?? "")} (end exclusive)</p></div>
    {comparison.available ? <dl className="grid grid-cols-3 gap-3 text-xs">
      <div><dt className="text-muted-foreground">Published</dt><dd className="num mt-1 font-medium">{number(comparison.baseline!, baseline.target.unit)}</dd></div>
      <div><dt className="text-muted-foreground">Scenario</dt><dd className="num mt-1 font-medium">{number(comparison.scenario!, baseline.target.unit)}</dd></div>
      <div><dt className="text-muted-foreground">Difference</dt><dd className="num mt-1 font-medium">{comparison.delta! > 0 ? "+" : ""}{number(comparison.delta!, baseline.target.unit)}</dd></div>
    </dl> : <p className="text-xs text-muted-foreground">{comparison.reason}</p>}
    {chart.length > 0 && <div className="h-40" role="img" aria-label="Published and hypothetical daily forecast for matching dates"><ResponsiveContainer width="100%" height="100%"><LineChart data={chart} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--border)"/><XAxis dataKey="date" tickFormatter={v => String(v).slice(5)} tick={{ fontSize: 10 }}/><YAxis tick={{ fontSize: 10 }} width={50}/><Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} formatter={v => number(Number(v), baseline.target.unit)}/><Line dataKey="baseline" name="Published" stroke="var(--muted-foreground)" strokeDasharray="4 3" dot={false}/><Line dataKey="scenario" name="Hypothetical" stroke="var(--chart-1)" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></div>}
    <p className="text-xs text-muted-foreground">{typeof range?.low === "number" && typeof range?.high === "number" ? `Scenario range: ${number(range.low, baseline.target.unit)}–${number(range.high, baseline.target.unit)}. Descriptive assumptions, not a confidence interval.` : "No scenario range is available for this total."} {range?.complete === false ? "The total has incomplete inputs. " : ""}Published forecast and budgets are unchanged.</p>
    {(baseline.is_synthetic || view?.is_synthetic) && <p className="text-xs text-muted-foreground">Only supplied assumptions are modeled.</p>}
    {chart.length > 0 && <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">View comparison table</summary><table className="mt-2 w-full text-left"><thead><tr><th className="py-1 font-medium">UTC date</th><th className="font-medium">Published</th><th className="font-medium">Hypothetical</th></tr></thead><tbody>{chart.map(p => <tr key={p.date} className="border-t border-border"><td className="py-1">{p.date}</td><td>{number(p.baseline, baseline.target.unit)}</td><td>{number(p.scenario, baseline.target.unit)}</td></tr>)}</tbody></table></details>}
  </section>;
}
