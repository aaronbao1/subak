import { Suspense } from "react";
import { UsagePage } from "@/components/usage/usage-page";
export default function Page() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">Loading usage activity…</p>}><UsagePage /></Suspense>;
}
