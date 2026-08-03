import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { MaturityBanner } from "@/components/MaturityBanner";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-0">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="border-b border-surface-border bg-surface-1">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3">
          <Link to="/scenarios" className="flex items-baseline gap-2">
            <span className="text-sm font-semibold tracking-tight text-ink-0">Ugence Governance Studio</span>
            <span className="text-xs text-ink-2">Eligibility Explorer</span>
          </Link>
          <span className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-ink-2">
            governance_studio.api.v1
          </span>
        </div>
      </header>
      <MaturityBanner />
      <main id="main-content" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5">
        {children}
      </main>
      <footer className="border-t border-surface-border px-4 py-3 text-center text-[11px] text-ink-3">
        Synthetic demonstration data · deterministic planning only · no agent execution · no
        permission granting · no business-action authorization
      </footer>
    </div>
  );
}
