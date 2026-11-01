/**
 * Navbar — top bar with the Aletheia brand identity.
 */

import AletheiaLogo from "./AletheiaLogo";

export default function Navbar() {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <AletheiaLogo compact />
          <div>
            <span className="text-orange-300 font-bold text-lg tracking-[0.12em]">ALETHEIA</span>
            <span className="ml-2 text-orange-200/60 text-xs font-medium hidden sm:inline">
              AI MEDIA PROVENANCE
            </span>
          </div>
        </div>

        {/* Status pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow" />
          <span className="text-emerald-400 text-xs font-semibold tracking-wide hidden sm:inline">
            Provenance Systems Online
          </span>
          <span className="text-emerald-400 text-xs font-semibold tracking-wide sm:hidden">
            v1.0
          </span>
        </div>
      </div>
    </header>
  );
}
