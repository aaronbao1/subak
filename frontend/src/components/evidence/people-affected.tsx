"use client";
import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { SIGNAL_LABEL } from "@/components/person/signal-badges";
import type { AffectedPerson } from "./derive";
import { Initials } from "./marks";

const LIMIT = 12;

/** Everyone the filtered evidence names, as initials on their team color. Each opens the person page; the latest signal is in the tooltip. */
export function PeopleAffected({ people }: { people: AffectedPerson[] }) {
  const [all, setAll] = useState(false);
  if (people.length === 0) return null;
  const shown = all ? people : people.slice(0, LIMIT);
  const more = people.length - shown.length;

  return (
    <section aria-labelledby="people-heading" className="rounded-xl border border-border bg-card px-5 py-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="people-heading" className="text-sm font-medium">People affected</h2>
        <span className="num text-xs text-muted-foreground">{people.length}</span>
      </div>
      <ul className="mt-3 flex flex-wrap items-center gap-1.5">
        {shown.map(({ person, team, item, more: extra }) => {
          const label = `${person.name}${team ? ` · ${team.name}` : ""} · ${item.signal ? SIGNAL_LABEL[item.signal] : item.title}${item.supersededBy ? " (superseded)" : ""}${extra > 0 ? ` +${extra}` : ""}`;
          return (
            <li key={person.id}>
              <Link href={`/teams/${person.teamId}/people/${person.id}`} title={label} aria-label={label} className="block rounded-full transition-opacity duration-300 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
                <Initials person={person} team={team} className={cn("size-7", item.supersededBy && "opacity-70")} />
              </Link>
            </li>
          );
        })}
        {more > 0 && (
          <li>
            <button type="button" onClick={() => setAll(true)} className="num flex size-7 items-center justify-center rounded-full bg-popover text-[10px] text-muted-foreground transition-colors duration-300 hover:text-foreground">
              +{more}
            </button>
          </li>
        )}
      </ul>
    </section>
  );
}
