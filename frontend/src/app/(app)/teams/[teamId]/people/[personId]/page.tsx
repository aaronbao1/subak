import { Suspense } from "react";
import { PersonDetail, PersonDetailSkeleton } from "@/components/person/person-detail";

type Params = Promise<{ teamId: string; personId: string }>;

/** Server page. `params` is awaited inside a Suspense boundary so navigation stays instant. */
export default function PersonPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<PersonDetailSkeleton />}>
      <ResolvedPerson params={params} />
    </Suspense>
  );
}

async function ResolvedPerson({ params }: { params: Params }) {
  const { teamId, personId } = await params;
  return <PersonDetail teamId={teamId} personId={personId} />;
}
