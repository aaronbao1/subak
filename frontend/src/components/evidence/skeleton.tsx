import { Skeleton } from "@/components/ui/skeleton";

/** Matches the page layout: title, the waterfall panel, the filter row, then the row feed beside the side panels. */
export function EvidenceSkeleton() {
  return (
    <div className="min-w-0 space-y-6" aria-busy="true" aria-label="Loading evidence">
      <Skeleton className="h-7 w-32" />
      <div className="flex flex-wrap items-end justify-between gap-6 rounded-xl border border-border bg-card p-5">
        <div className="space-y-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-8 w-36" />
        </div>
        <div className="flex h-24 w-full max-w-[420px] items-end justify-around">
          {[80, 12, 8, 90].map((h, i) => <Skeleton key={i} className="w-6" style={{ height: `${h}%` }} />)}
        </div>
      </div>
      <Skeleton className="h-8 w-[560px] max-w-full" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <div className="space-y-3 rounded-xl border border-border bg-card p-4">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-3 rounded-xl border border-border bg-card px-5 py-4">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
