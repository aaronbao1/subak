import { Suspense } from "react";
import { TeamDetail, TeamDetailSkeleton } from "@/components/team/team-detail";

/** Server page. `params` is awaited inside a Suspense boundary so navigation stays instant (Next 16 instant shell). */
export default function TeamPage({ params }: PageProps<"/teams/[teamId]">) {
  return (
    <Suspense fallback={<TeamDetailSkeleton />}>
      <ResolvedTeam params={params} />
    </Suspense>
  );
}

async function ResolvedTeam({ params }: { params: PageProps<"/teams/[teamId]">["params"] }) {
  const { teamId } = await params;
  return <TeamDetail teamId={teamId} />;
}
