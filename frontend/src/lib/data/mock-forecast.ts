import type { ForecastBundle, ForecastDriver, ForecastPoint, ForecastView } from '@/lib/contracts';
import type { Dataset } from '@/fixtures';
import { DEMO_NOW } from '@/fixtures/generate';
import { billableAmount, sumMoney } from '@/lib/finance-summary';

const day = (date: string, n: number) => new Date(Date.parse(`${date}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
const countDays = (a:string,b:string) => Math.max(0,Math.round((Date.parse(b)-Date.parse(a))/86400000));
/** Explicit scope only. Project/configuration scope needs a supplied mapping; unknown is never global. */
function driverApplies(driver: ForecastDriver, scope: ForecastView['scope'], people: Dataset['people']): boolean {
  if (scope.type === 'company') return true;
  const record = (value: unknown): Record<string, unknown> | undefined => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
  const affected = driver.affected_scopes ?? driver.applicable_scopes;
  if (Array.isArray(affected) && affected.length) {
    return affected.some(value => { const item = record(value); return item?.type === scope.type && item.id === scope.id; });
  }
  const source = record(driver.scope);
  if (!source || !Object.keys(source).length) return false;
  if (source.type === 'company') return true;
  const ids = (kind: 'team' | 'person' | 'shared'): string[] => {
    const single = source.type === kind ? source.id : source[`${kind}_id`];
    const multiple = source[`${kind}_ids`];
    return [...(typeof single === 'string' ? [single] : []), ...(Array.isArray(multiple) ? multiple.filter((id): id is string => typeof id === 'string') : [])];
  };
  const teams = ids('team'), persons = ids('person');
  if (scope.type === 'shared') return ids('shared').includes(scope.id ?? '');
  const affectedPeople = people.filter(person => (persons.length > 0 || teams.length > 0) && (!persons.length || persons.includes(person.id)) && (!teams.length || teams.includes(person.teamId)));
  if (scope.type === 'person') return affectedPeople.some(person => person.id === scope.id);
  if (affectedPeople.some(person => person.teamId === scope.id) || !persons.length && teams.includes(scope.id ?? '')) return true;
  // A membership assumption affects both the old team and the explicit new team,
  // but does not become an assumption about every person already on the new team.
  return driver.kind === 'membership' && driver.parameters?.team_id === scope.id && (persons.length > 0 || teams.length > 0);
}

/** Frozen, explicitly synthetic demo. Supplied weekly fixtures are authoritative; no uncertainty is invented. */
export function syntheticForecastBundle(fx: Dataset, runId = 'synthetic-ui-run-1', drivers?: ForecastDriver[]): ForecastBundle {
  const start = DEMO_NOW.slice(0,10);
  const monday = day(start,-((new Date(`${start}T00:00:00Z`).getUTCDay()+6)%7));
  const period = fx.company.currentPeriod;
  const periodEnd = day(period.end,1);
  const quarterMonth = Math.floor((Number(start.slice(5,7))-1)/3)*3;
  const quarterStart = new Date(Date.UTC(Number(start.slice(0,4)),quarterMonth,1)).toISOString().slice(0,10);
  const quarterEnd = new Date(Date.UTC(Number(start.slice(0,4)),quarterMonth+3,1)).toISOString().slice(0,10);
  const scopes = [
    ...fx.teams.map(t => ({type:'team' as const,id:t.id,name:t.name})),
    ...fx.people.map(p => ({type:'person' as const,id:p.id,name:p.name})),
    {type:'shared' as const,id:'shared',name:'Company shared / unattributed'},
    {type:'shared' as const,id:'people_unallocated',name:'Team usage without person attribution'},
    {type:'shared' as const,id:'teams_unallocated',name:'Person usage without team attribution'},
  ];
  const history = fx.spending.filter(r=>r.complete && r.date < start);
  const dates = new Set(history.map(r=>r.date));
  const quarterCovered = Array.from({length:countDays(quarterStart,start)},(_,i)=>day(quarterStart,i)).every(d=>dates.has(d));
  const publication = {generated_at:DEMO_NOW,information_cutoff:`${start}T00:00:00Z`,history_complete_through:day(start,-1),forecast_start:start};
  const forecasts = fx.forecasts ?? [];
  const views:ForecastView[] = scopes.map(scope=>{
    const matches = (r:Dataset['spending'][number]) => scope.type === 'team' ? r.teamId === scope.id : scope.type === 'person' ? r.personId === scope.id : scope.id === 'people_unallocated' ? !!r.teamId && !r.personId : scope.id === 'teams_unallocated' ? !r.teamId && !!r.personId : !r.teamId && !r.personId;
    const rows=history.filter(matches);
    const recorded=sumMoney(rows.filter(r=>r.date>=period.start&&r.date<periodEnd).map(billableAmount));
    const quarterRecorded=sumMoney(rows.filter(r=>r.date>=quarterStart).map(billableAmount));
    const rate=dates.size ? sumMoney(rows.map(billableAmount))/dates.size : 0;
    const supplied=forecasts.find(f=>f.period.start===period.start && f.period.end===period.end && (scope.type==='team' ? f.teamId===scope.id&&!f.personId : scope.type==='person'&&f.personId===scope.id));
    const unavailable=!!supplied&&supplied.status!=='available';
    const planned=unavailable ? null : supplied?.projected ?? sumMoney([recorded,rate*countDays(start,periodEnd)]);
    // The supplied total is authoritative. Reconcile the supplied daily weights to its remaining amount.
    const suppliedDays=(supplied?.daily??[]).filter(d=>d.date>=start&&d.date<periodEnd);
    const remaining=planned === null ? null : Math.max(0,sumMoney([planned,-recorded]));
    const weights=Array.from({length:countDays(start,periodEnd)},(_,i)=>suppliedDays.find(d=>d.date===day(start,i))?.projected??1);
    const weightTotal=weights.reduce((a,b)=>a+b,0);
    const periodDaily=weights.map(w=>remaining===null?null:Math.round(remaining*(weightTotal?w/weightTotal:1/weights.length)*100)/100);
    if(periodDaily.length && remaining!==null) periodDaily[0]=sumMoney([periodDaily[0]??0,remaining,-sumMoney(periodDaily.map(x=>x??0))]);
    const futureAmount=(date:string):number|null => unavailable ? null : date>=start&&date<periodEnd ? periodDaily[countDays(start,date)]??0 : Math.round(rate*100)/100;
    const point=(a:string,b:string):ForecastPoint=>{const amounts=Array.from({length:countDays(a,b)},(_,i)=>futureAmount(day(a,i)));return {start:a,end:b,base:amounts.some(x=>x===null)?null:sumMoney(amounts as number[]),low:null,high:null,recorded:0};};
    const daily=Array.from({length:7},(_,i)=>({...point(day(start,i),day(start,i+1)),date:day(start,i)}));
    const weekly=Array.from({length:4},(_,i)=>({...point(i===0?start:day(monday,i*7),day(monday,i*7+7)),calendar_start:day(monday,i*7),partial:i===0&&start!==monday,label:i===0&&start!==monday?'Partial first forecast week':'Monday–Sunday'}));
    const cumulative=Array.from({length:countDays(start,day(monday,28))},(_,i)=>{const p=point(start,day(start,i+1));return {...p,start:period.start,date:day(start,i),base:p.base===null?null:sumMoney([recorded,p.base??0])};});
    const quarterFuture=point(start,quarterEnd).base;
    return {run_id:runId,id:`${runId}:${scope.type}:${scope.id}`,scope,dataset_id:fx.company.id,...(scope.type==='person'?{team_id:fx.people.find(p=>p.id===scope.id)?.teamId}:{}),target:{unit:fx.company.budgetUnit,quantity:'spend',basis:'planning',timezone:'UTC'},timezone:'UTC',procedure_version:'synthetic-ui-fixture',publication,information_cutoff:publication.information_cutoff,forecast_start:start,components:{recorded,late:0,future:remaining,fixed:0},daily,weekly,cumulative,planning_period_outlook:{start:period.start,end:periodEnd,base:planned,low:null,high:null,label:period.label??'Planning period'},quarter_outlook:{start:quarterStart,end:quarterEnd,base:quarterCovered&&quarterFuture!==null?sumMoney([quarterRecorded,quarterFuture??0]):null,low:null,high:null,complete:quarterCovered&&!unavailable,label:'Synthetic quarter continuation',assumptions:['Supplied synthetic planning totals, then constant observed-rate continuation. No numerical forecast engine or calibration has run.']},included_drivers:(drivers??[]).filter(driver=>driverApplies(driver,scope,fx.people)),queued_changes:[],driver_effects:[],historical_error_interval:null,scenario_range:{status:'unavailable',reason:'No scenario bounds in this synthetic UI fixture.'},limitations:['Synthetic illustration with supplied weekly totals; no forecast engine or calibration has run.',...(quarterCovered?[]:['Earlier quarter observations are unavailable, so the quarter total is withheld.'])],is_synthetic:true};
  });
  const parts=views.filter(v=>v.scope.type==='team'||v.scope.type==='shared'&&(v.scope.id==='shared'||v.scope.id==='teams_unallocated'));
  const sum=(values:unknown[])=>values.some(v=>typeof v!=='number'||!Number.isFinite(v))?null:sumMoney(values as number[]);
  const template=views[0];
  // Company is an explicit additive partition, including unattributed charges and unavailable components.
  if(template) {
    const company:ForecastView={...template,id:`${runId}:company:${fx.company.id}`,scope:{type:'company',id:fx.company.id,name:fx.company.name},included_drivers:drivers??[],components:{recorded:sum(parts.map(v=>v.components?.recorded)),late:0,future:sum(parts.map(v=>v.components?.future)),fixed:0},daily:template.daily.map((p,i)=>({...p,base:sum(parts.map(v=>v.daily[i]?.base))})),weekly:template.weekly.map((p,i)=>({...p,base:sum(parts.map(v=>v.weekly[i]?.base))})),cumulative:template.cumulative.map((p,i)=>({...p,base:sum(parts.map(v=>v.cumulative[i]?.base))})),planning_period_outlook:{...(template.planning_period_outlook as object),base:sum(parts.map(v=>(v.planning_period_outlook as Record<string,unknown>).base))},quarter_outlook:{...template.quarter_outlook,base:sum(parts.map(v=>v.quarter_outlook?.base))}};
    views.unshift(company);
  }
  return {views,driver_effects:[],publication:{run_id:runId,published_at:DEMO_NOW}};
}
