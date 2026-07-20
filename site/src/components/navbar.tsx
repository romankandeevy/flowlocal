import { Mic } from "lucide-react";
import { ModeToggle } from "@/components/mode-toggle";

export function Navbar() {
  return (
    <header className="sticky top-2 z-40 mx-auto mt-3 mb-0 flex w-full max-w-[980px] items-center justify-between rounded-[var(--radius-lg)] border border-border bg-paper/85 px-5 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-2.5">
        <span className="grid size-7 place-items-center rounded-[var(--radius-sm)] bg-ink">
          <Mic className="size-4 text-paper" />
        </span>
        <span className="text-lg font-bold tracking-tight">FlowLocal</span>
      </div>
      <ModeToggle />
    </header>
  );
}
