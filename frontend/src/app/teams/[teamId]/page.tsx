/** PLACEHOLDER — team workstream. */
export default async function TeamPage({ params }: PageProps<"/teams/[teamId]">) {
  const { teamId } = await params;
  return <div className="text-sm text-muted-foreground">Team drilldown for {teamId} goes here.</div>;
}
