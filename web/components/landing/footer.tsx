import { Wordmark } from "@/components/brand/wordmark";

export function LandingFooter() {
  return (
    <footer className="border-t border-line bg-bg-panel px-6 py-10 md:px-12">
      <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <Wordmark />
          <span className="hidden text-[11px] text-text-faint sm:inline">
            Resonant Modal Spectroscopy diagnostics
          </span>
        </div>
        <div className="flex flex-wrap gap-6 text-[12px] text-text-muted">
          <a href="https://github.com/Yashasnagraj/UNISYS" className="hover:text-text transition-colors">
            GitHub
          </a>
          <a href="/dashboard/scan" className="hover:text-text transition-colors">
            Live Demo
          </a>
          <span>Patent pending</span>
          <span>Built for UNISYS 2026</span>
        </div>
      </div>
    </footer>
  );
}
