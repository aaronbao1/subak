import { Suspense } from "react";
import { EvidencePage } from "@/components/evidence/evidence-page";
import { EvidenceSkeleton } from "@/components/evidence/skeleton";

/** Server page. The client view reads `useSearchParams`, so it sits inside its own Suspense boundary (cacheComponents is on). */
export default function Page() {
  return (
    <Suspense fallback={<EvidenceSkeleton />}>
      <EvidencePage />
    </Suspense>
  );
}
