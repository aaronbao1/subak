import { Suspense } from "react";
import { AppShell } from "@/components/shell/app-shell";

/** Product routes: the shared top header, the page, and the assistant drawer. The marketing landing lives outside this group. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AppShell>
        <div className="mx-auto w-full max-w-[1440px] space-y-6 p-4 sm:p-6 lg:px-8">{children}</div>
      </AppShell>
    </Suspense>
  );
}
