"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { SIGNAL_LABEL } from "@/components/person/signal-badges";
import type { AffectedPerson } from "./derive";

/** Everyone the filtered evidence names, with their team and the newest signal about them. Rows open the person page. */
export function PeopleAffected({ people }: { people: AffectedPerson[] }) {
  return (
    <section aria-labelledby="people-heading" className="rounded-xl border border-border bg-card">
      <header className="px-5 pt-5 pb-3">
        <h2 id="people-heading" className="text-base font-medium">People affected</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Individuals named in the evidence shown, with the latest signal about each.</p>
      </header>
      {people.length === 0 ? (
        <div className="border-t border-border px-5 py-6">
          <div className="eyebrow">No one named</div>
          <p className="mt-1.5 text-sm text-muted-foreground">The evidence shown is about teams or the company, not individuals.</p>
        </div>
      ) : (
        <ul className="divide-y divide-border border-t border-border">
          {people.map(({ person, team, item, more }) => (
            <li key={person.id}>
              <Link
                href={`/teams/${person.teamId}/people/${person.id}`}
                className="group flex items-center gap-3 px-5 py-2.5 transition-colors duration-300 hover:bg-popover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset"
              >
                <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: team?.color ?? "var(--border-strong)" }} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="truncate text-sm">{person.name}</span>
                    {team && <span className="truncate text-xs text-muted-foreground">{team.name}</span>}
                  </span>
                  <span className={cn("mt-0.5 block truncate text-xs", item.supersededBy ? "text-muted-foreground line-through" : "text-foreground/80")}>
                    {item.signal ? SIGNAL_LABEL[item.signal] : item.title}
                    {more > 0 && <span className="num text-muted-foreground no-underline"> +{more}</span>}
                  </span>
                </span>
                <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-foreground" aria-hidden strokeWidth={1.5} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
