/**
 * ForensicsBreakdown.jsx — Per-detector AI Forensics result display.
 *
 * Renders:
 *   - Ensemble AI probability gauge
 *   - Per-detector score bars with confidence indicators
 *   - Detector reason text
 *   - Provenance evidence sub-panel (when available)
 */

import { Cpu, BarChart2, Layers, Zap, Brain, Activity } from "lucide-react";

/* ── Detector icon mapping ─────────────────────────────────────────── */
const DETECTOR_ICONS = {
  foundation_clip:      Brain,
  statistical_features: BarChart2,
  artifact_cv:          Layers,
  frequency_spectral:   Zap,
};

/* ── Score color ────────────────────────────────────────────────────── */
function scoreColor(score) {
  if (score < 0.35) return { bar: "bg-emerald-500/70", text: "text-emerald-400" };
  if (score < 0.65) return { bar: "bg-amber-500/70",   text: "text-amber-400" };
  return              { bar: "bg-red-500/70",     text: "text-red-400" };
}

/* ── Detector row ───────────────────────────────────────────────────── */
function DetectorRow({ detector }) {
  const Icon = DETECTOR_ICONS[detector.engine] ?? Cpu;
  const colors = scoreColor(detector.score);
  const scorePercent = Math.round(detector.score * 100);
  const confPercent  = Math.round(detector.confidence * 100);

  // Human-readable engine label
  const ENGINE_LABELS = {
    foundation_clip:      "Foundation (CLIP)",
    statistical_features: "Statistical Features",
    artifact_cv:          "Artifact CV",
    frequency_spectral:   "Frequency Spectral",
  };
  const label = ENGINE_LABELS[detector.engine] ?? detector.engine;

  return (
    <div className="py-3.5 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-7 h-7 rounded-md bg-white/[0.04] border border-white/[0.07] flex items-center justify-center shrink-0">
          <Icon className="w-3.5 h-3.5 text-slate-400" strokeWidth={1.8} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300">{label}</span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-600">conf {confPercent}%</span>
              <span className={`text-xs font-black tabular-nums ${colors.text}`}>
                {scorePercent}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Score bar */}
      <div className="ml-10">
        <div className="h-1.5 rounded-full bg-white/[0.05] overflow-hidden mb-1.5">
          <div
            className={`h-full rounded-full transition-all duration-700 ${colors.bar}`}
            style={{ width: `${scorePercent}%` }}
          />
        </div>
        <p className="text-[11px] text-slate-500 leading-snug">{detector.reason}</p>
      </div>
    </div>
  );
}

/* ── Provenance sub-panel ───────────────────────────────────────────── */
function ProvenancePanel({ evidence }) {
  if (!evidence) return null;

  return (
    <div className="glass-card px-5 py-4 mt-4">
      <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-3 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5" />
        Provenance Evidence
      </p>

      <div className="space-y-1.5 text-xs">
        {/* MIR status */}
        <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
          <span className="text-slate-500">Watermark Recovered</span>
          <span className={`font-bold ${evidence.mir_recovered ? "text-emerald-400" : "text-red-400"}`}>
            {evidence.mir_recovered ? "Yes" : "No"}
          </span>
        </div>

        {/* Verification */}
        <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
          <span className="text-slate-500">Verification Status</span>
          <span className={`font-bold ${evidence.available ? "text-emerald-400" : "text-slate-400"}`}>
            {evidence.available ? "Verified" : evidence.mir_recovered ? "Unregistered" : "No Watermark"}
          </span>
        </div>

        {evidence.integrity_score != null && (
          <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
            <span className="text-slate-500">Integrity Score</span>
            <span className="font-bold text-slate-200">{evidence.integrity_score} / 100</span>
          </div>
        )}

        {evidence.similarity != null && (
          <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
            <span className="text-slate-500">pHash Similarity</span>
            <span className="font-bold text-slate-200">{evidence.similarity.toFixed(1)}%</span>
          </div>
        )}

        {evidence.hamming_distance != null && (
          <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
            <span className="text-slate-500">Hamming Distance</span>
            <span className="font-mono font-bold text-slate-200">{evidence.hamming_distance} / 64 bits</span>
          </div>
        )}

        {evidence.recovered_regions != null && (
          <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
            <span className="text-slate-500">ADPE Regions</span>
            <span className="font-bold text-slate-200">
              {evidence.recovered_regions} / {evidence.total_regions} recovered
            </span>
          </div>
        )}

        {evidence.media_id && (
          <div className="flex items-start justify-between gap-3 py-1.5">
            <span className="text-slate-500 shrink-0">Media ID</span>
            <span className="font-mono text-[10px] text-slate-400 text-right break-all">
              {evidence.media_id}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Component ────────────────────────────────────────────────── */
export default function ForensicsBreakdown({ report }) {
  const { detector_breakdown, forensics_evidence, provenance_evidence } = report;

  const aiPercent = Math.round(report.ai_probability * 100);
  const aiColor = scoreColor(report.ai_probability);

  return (
    <div className="space-y-4">

      {/* ── Ensemble AI probability ── */}
      <div className="glass-card px-5 py-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-2">
            <Cpu className="w-3.5 h-3.5" />
            AI Forensics Engine
          </p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Verdict:</span>
            <span className={`text-xs font-bold ${aiColor.text}`}>{report.forensics_verdict}</span>
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-medium">Ensemble AI Probability</span>
            <span className={`font-black tabular-nums ${aiColor.text}`}>{aiPercent}%</span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.05] overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${aiColor.bar}`}
              style={{ width: `${aiPercent}%` }}
            />
          </div>
          {forensics_evidence && (
            <p className="text-[11px] text-slate-600 pt-1">
              {forensics_evidence.detector_count} detectors ·{" "}
              {(forensics_evidence.confidence * 100).toFixed(1)}% confidence
            </p>
          )}
        </div>
      </div>

      {/* ── Per-detector breakdown ── */}
      {detector_breakdown?.length > 0 && (
        <div className="glass-card px-5 py-2">
          <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest pt-3 pb-1">
            Detector Breakdown
          </p>
          {detector_breakdown.map((det) => (
            <DetectorRow key={det.engine} detector={det} />
          ))}
        </div>
      )}

      {/* ── Provenance evidence ── */}
      <ProvenancePanel evidence={provenance_evidence} />

      {/* ── Reasoning ── */}
      {report.reasoning && (
        <details className="glass-card px-5 py-4 cursor-pointer group">
          <summary className="text-[10px] font-bold text-slate-600 uppercase tracking-widest list-none flex items-center justify-between">
            <span>Full Decision Reasoning</span>
            <span className="text-slate-700 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <pre className="mt-3 text-[11px] text-slate-500 leading-relaxed whitespace-pre-wrap font-mono break-words overflow-auto max-h-64">
            {report.reasoning}
          </pre>
        </details>
      )}
    </div>
  );
}
