import { Suspense } from "react";
import { RequestsPage } from "@/components/requests/requests-page";
export default function Page() { return <Suspense fallback={<p className="text-sm text-muted-foreground">Loading requests…</p>}><RequestsPage /></Suspense>; }
