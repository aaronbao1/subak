"use client";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAppStore } from "@/lib/store";

/** PLACEHOLDER — assistant workstream replaces the body. Keep the Sheet + store wiring. */
export function AssistantDrawer() {
  const { assistantOpen, setAssistantOpen } = useAppStore();
  return (
    <Sheet open={assistantOpen} onOpenChange={setAssistantOpen}>
      <SheetContent side="right" className="w-[440px] sm:max-w-[440px]">
        <SheetHeader><SheetTitle>Assistant</SheetTitle></SheetHeader>
        <div className="p-4 text-sm text-muted-foreground">Assistant panel goes here.</div>
      </SheetContent>
    </Sheet>
  );
}
