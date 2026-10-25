"use client";

import { useMemo, useState } from "react";
import type { Period, SpendingRecord, Team } from "@/lib/contracts";
import { buildDailySpendData, recordedDailyExtent } from "./daily-spend-data";
import { dateLabel, teamKey } from "./derive";
import { SpendByTeamChart } from "./spend-by-team-chart";

export interface DailySpendByTeamProps {
  records: SpendingRecord[];
  teams: Team[];
  period: Period;
  unit?: "usd";
}

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/** The overview shows recorded USD only; all future and unreported amounts stay empty. */
export function DailySpendByTeam({ records, teams, period, unit = "usd" }: DailySpendByTeamProps) {
  const data = useMemo(() => buildDailySpendData(records, teams, period), [records, teams, period]);
  const rows = useMemo(() => recordedDailyExtent(data.rows), [data.rows]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const recordedDays = data.rows.filter(row => row.kind === "recorded");
  const qualification = [
    data.hasEstimates ? "Estimated amounts are included." : "",
    data.hasUnpricedUsage ? "Usage without a dollar price is excluded." : "",
    data.invalidAmountCount > 0 ? `${data.invalidAmountCount} ${data.invalidAmountCount === 1 ? "record has" : "records have"} no valid dollar amount.` : "",
  ].filter(Boolean).join(" ");

  return <SpendByTeamChart
    teams={data.teams} rows={rows} partialDates={data.partialDates}
    unit={unit} period={period} compact periodOnly
    selectedId={selectedId}
    onSelect={id => setSelectedId(current => current === id ? null : id)}
    note={qualification}
    details={recordedDays.length > 0 ? <details className="border-t border-border pt-2 text-xs">
      <summary className="w-fit cursor-pointer text-muted-foreground hover:text-foreground">View daily amounts</summary>
      <div className="mt-2 max-h-72 overflow-auto rounded-md border border-border">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Daily spending by team in USD for {period.start} through {period.end}. A dash means no recorded amount.</caption>
          <thead className="sticky top-0 bg-card">
            <tr><th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Date</th>{data.teams.map(team => <th key={team.id} scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">{team.name}</th>)}</tr>
          </thead>
          <tbody>{recordedDays.map(row => <tr key={row.date} className="border-t border-border">
            <th scope="row" className="whitespace-nowrap px-3 py-2 font-normal">{dateLabel(row.date)}{row.partial ? " · partial" : ""}</th>
            {data.teams.map(team => {
              const amount = row[teamKey(team.id)];
              return <td key={team.id} className="num whitespace-nowrap px-3 py-2 text-right">{typeof amount === "number" ? dollars.format(amount) : <span aria-label="No recorded amount">—</span>}</td>;
            })}
          </tr>)}</tbody>
        </table>
      </div>
    </details> : undefined}
  />;
}
