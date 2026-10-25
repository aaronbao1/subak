import type { ForecastBundle, ForecastDriver, ForecastPoint, ForecastView } from "@/lib/contracts";
import type { Dataset } from "@/fixtures";

const day = (date: string, n: number) => new Date(Date.parse(`${date}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
/** UI fixtures only. Bounds and error intervals intentionally stay unavailable. */
export function syntheticForecastBundle(fx: Dataset, runId = "synthetic-ui-run-1", drivers?: ForecastDriver[]): ForecastBundle {
  const start = "2026-10-24";
  const monday = day(start, -5);
  const scopes = [
    { type: "company" as const, id: fx.company.id, name: fx.company.name },
    ...fx.teams.map(t => ({ type: "team" as const, id: t.id, name: t.name })),
    ...fx.people.map(p => ({ type: "person" as const, id: p.id, name: p.name })),
    { type: "shared" as const, id: "shared", name: "Company shared / unattributed" },
    { type: "shared" as const, id: "people_unallocated", name: "Team usage without person attribution" },
    { type: "shared" as const, id: "teams_unallocated", name: "Person usage without team attribution" },
  ];
  const historyDayCount = new Set(fx.spending.filter(r=>r.complete).map(r=>r.date)).size;
  const views: ForecastView[] = scopes.map(scope => {
    const rows = fx.spending.filter(r => r.complete && (scope.type === "company" || scope.type === "team" && r.teamId === scope.id || scope.type === "person" && r.personId === scope.id || scope.type === "shared" && (scope.id === "shared" ? !r.personId && !r.teamId : scope.id === "people_unallocated" ? !r.personId && !!r.teamId : !!r.personId && !r.teamId)));
    const byDay = new Map<string, number>();
    for (const r of rows) byDay.set(r.date, (byDay.get(r.date) ?? 0) + r.amount);
    const rate = historyDayCount ? [...byDay.values()].reduce((a,b) => a+b,0) / historyDayCount : 0;
    const point = (a: string, b: string, n: number): ForecastPoint => ({ start:a, end:b, base:rate*n, low:null, high:null, complete:true, recorded:0, future:rate*n });
    const daily = Array.from({length:7}, (_,i) => ({...point(day(start,i),day(start,i+1),1),date:day(start,i)}));
    const weekly = Array.from({length:4}, (_,i) => ({...point(i===0 ? start : day(monday,i*7),day(monday,i*7+7),i===0 ? 2 : 7), calendar_start:day(monday,i*7),partial:i===0, label:i===0 ? "Partial first forecast week" : "Monday–Sunday"}));
    const recorded = rows.filter(r => r.date >= fx.company.currentPeriod.start && r.date < start).reduce((a,r)=>a+r.amount,0);
    const cumulative = Array.from({length:23}, (_,i)=>({...point(fx.company.currentPeriod.start,day(start,i+1),i+1),date:day(start,i),base:recorded+rate*(i+1)}));
    const remaining = Math.max(0, (Date.parse("2027-01-01")-Date.parse(start))/86400000);
    return { run_id:runId, id:`${runId}:${scope.type}:${scope.id}`, scope, target:{unit:fx.company.budgetUnit,quantity:"spend",basis:"planning",timezone:"UTC"}, timezone:"UTC", procedure_version:"synthetic-ui-fixture", publication:{generated_at:"2026-10-24T00:00:00Z",information_cutoff:"2026-10-24T00:00:00Z",history_complete_through:"2026-10-23",forecast_start:start}, components:{recorded,late:null,future:rate*remaining,fixed:null}, daily, weekly, cumulative, quarter_outlook:{start:fx.company.currentPeriod.start,end:"2027-01-01",base:recorded+rate*remaining,low:null,high:null,complete:false,label:"Conditional quarter continuation",assumptions:["Synthetic constant-rate illustration; no numerical model or calibration has run."]}, included_drivers:drivers ?? [],queued_changes:[],historical_error_interval:null,scenario_range:{status:"unavailable",reason:"No scenario bounds in this synthetic UI fixture."},limitations:["Synthetic UI fixture. Values illustrate interface behavior, not enterprise accuracy.","Late charges and fixed costs are unknown; quarter is incomplete."],is_synthetic:true };
  });
  return {views,driver_effects:[],publication:{run_id:runId,published_at:"2026-10-24T00:00:00Z"}};
}
