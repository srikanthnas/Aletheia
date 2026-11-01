/**
 * TrustScoreCard.jsx — Displays the Trust & Decision Engine output.
 *
 * Renders:
 *   - Trust Score gauge (0–100) with animated progress arc
 *   - Final verdict badge with color coding
 *   - Confidence indicator
 *   - Layer summary (Provenance + Forensics)
 *   - Evidence bullet list
 */

import { ShieldCheck, ShieldAlert, ShieldX, ShieldQuestion, Activity } from "lucide-react";

/* ── Verdict configuration ─────────────────────────────────────────── */
const VERDICT_CONFIG = {
  AUTHENTIC: {
    label: "Authentic",
    icon: ShieldCheck,
    color: "emerald",
    ring:  "border-emerald-500/40",
    bg:    "bg-emerald-500/10",
    badge: "bg-emerald-500/20 border-emerald-500/40 text-emerald-300",
    text:  "text-emerald-400",
    glow:  "shadow-emerald-900/40",
    arc:   "#10b981",
  },
  AI_GENERATED: {
    label: "AI Generated",
    icon: ShieldX,
    color: "red",
    ring:  "border-red-500/40",
    bg:    "bg-red-500/10",
    badge: "bg-red-500/20 border-red-500/40 text-red-300",
    text:  "text-red-400",
    glow:  "shadow-red-900/40",
    arc:   "#ef4444",
  },
  MODIFIED: {
    label: "Modified",
    icon: ShieldAlert,
    color: "orange",
    ring:  "border-orange-500/40",
    bg:    "bg-orange-500/10",
    badge: "bg-orange-500/20 border-orange-500/40 text-orange-300",
    text:  "text-orange-400",
    glow:  "shadow-orange-900/40",
    arc:   "#f97316",
  },
  TAMPERED: {
    label: "Tampered",
    icon: ShieldX,
    color: "red",
    ring:  "border-red-600/50",
    bg:    "bg-red-600/10",
    badge: "bg-red-600/20 border-red-600/40 text-red-200",
    text:  "text-red-400",
    glow:  "shadow-red-900/50",
    arc:   "#dc2626",
  },
  SUSPICIOUS: {
    label: "Suspicious",
    icon: ShieldAlert,
    color: "amber",
    ring:  "border-amber-500/40",
    bg:    "bg-amber-500/10",
    badge: "bg-amber-500/20 border-amber-500/40 text-amber-300",
    text:  "text-amber-400",
    glow:  "shadow-amber-900/40",
    arc:   "#f59e0b",
  },
  UNVERIFIED: {
    label: "Unverified",
    icon: ShieldQuestion,
    color: "slate",
    ring:  "border-slate-500/30",
    bg:    "bg-slate-500/10",
    badge: "bg-slate-500/20 border-slate-500/30 text-slate-400",
    text:  "text-slate-400",
    glow:  "shadow-slate-900/20",
    arc:   "#64748b",
  },
};

/* ── SVG Trust Score Gauge ─────────────────────────────────────────── */
function TrustGauge({ score, color }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - score / 100);

  return (
    <div className="relative flex items-center justify-center w-36 h-36">
      <svg className="absolute" width="144" height="144" viewBox="0 0 144 144">
        {/* Track */}
        <circle
          cx="72" cy="72" r={radius}
          fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10"
        />
        {/* Progress arc */}
        <circle
          cx="72" cy="72" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          transform="rotate(-90 72 72)"
          style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)" }}
        />
      </svg>
      <div className="text-center z-10">
        <span className="text-4xl font-black text-slate-100 tabular-nums">{score}</span>
        <span className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">/ 100</span>
      </div>
    </div>
  );
}

/* ── Layer Pill ────────────────────────────────────────────────────── */
function LayerPill({ label, value, available }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
      <span className="text-xs text-slate-500 font-medium">{label}</span>
      <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
        available
          ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-400"
          : "bg-slate-700/40 border-slate-600/30 text-slate-400"
      }`}>
        {value ?? "—"}
      </span>
    </div>
  );
}

/* ── Main Component ────────────────────────────────────────────────── */
export default function TrustScoreCard({ report }) {
  const cfg = VERDICT_CONFIG[report.verdict] ?? VERDICT_CONFIG.UNVERIFIED;
  const VerdictIcon = cfg.icon;

  return (
    <div className="space-y-5 animate-slide-up">

      {/* ── Primary verdict card ── */}
      <div className={`rounded-2xl border p-6 ${cfg.ring} ${cfg.bg}`}>
        <div className="flex flex-col sm:flex-row items-center gap-6">

          {/* Gauge */}
          <div className="shrink-0">
            <TrustGauge score={report.trust_score} color={cfg.arc} />
            <p className="text-center text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">
              Trust Score
            </p>
          </div>

          {/* Verdict info */}
          <div className="flex-1 min-w-0 text-center sm:text-left">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold uppercase tracking-widest mb-3 ${cfg.badge}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${cfg.text.replace("text-", "bg-")}`} />
              {cfg.label}
            </div>

            <div className="flex items-center gap-2 mb-3">
              <VerdictIcon className={`w-8 h-8 ${cfg.text}`} strokeWidth={1.5} />
              <h2 className="text-2xl font-black text-slate-100">{report.verdict.replace("_", " ")}</h2>
            </div>

            {/* Confidence bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500 font-medium">Engine Confidence</span>
                <span className={`font-bold ${cfg.text}`}>{(report.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${report.confidence * 100}%`, backgroundColor: cfg.arc }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Layer summary ── */}
      <div className="glass-card px-5 py-4">
        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-3 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5" />
          Evidence Layer Summary
        </p>
        <LayerPill
          label="Layer 1 — Provenance"
          value={report.provenance_verdict ?? (report.provenance_available ? "VERIFIED" : "NOT FOUND")}
          available={report.provenance_available}
        />
        <LayerPill
          label="Layer 2 — AI Forensics"
          value={`${report.forensics_verdict} (${(report.ai_probability * 100).toFixed(0)}% AI)`}
          available={true}
        />
        {report.integrity_score != null && (
          <LayerPill
            label="Integrity Score"
            value={`${report.integrity_score} / 100`}
            available={report.integrity_score >= 85}
          />
        )}
        {report.provenance_evidence?.local_similarity != null && (
          <LayerPill
            label="Local Structural Integrity"
            value={`${report.provenance_evidence.local_similarity.toFixed(1)}%`}
            available={report.provenance_evidence.local_similarity >= 85}
          />
        )}
        {report.provenance_evidence?.tamper_type && report.provenance_evidence.tamper_type !== "NONE" && (
          <LayerPill
            label="Modification Assessment"
            value={report.provenance_evidence.tamper_type}
            available={false}
          />
        )}
        {report.provenance_evidence?.pixel_hash_match != null && (
          <LayerPill
            label="Exact Pixel Integrity"
            value={report.provenance_evidence.pixel_hash_match ? "MATCH" : "MISMATCH"}
            available={report.provenance_evidence.pixel_hash_match}
          />
        )}
      </div>

      {/* ── Evidence chain ── */}
      {report.evidence_summary?.length > 0 && (
        <div className="glass-card px-5 py-4">
          <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-3">
            Evidence Chain
          </p>
          <ol className="space-y-2">
            {report.evidence_summary.map((bullet, i) => (
              <li key={i} className="flex gap-3 text-sm text-slate-400 leading-relaxed">
                <span className="shrink-0 w-5 h-5 rounded-full bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-[10px] font-bold text-slate-500">
                  {i + 1}
                </span>
                {bullet}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
