/**
 * VerifyPanel — Sprint 3 UI component.
 *
 * Shown after successful embedding. Fetches the embedded image from the
 * backend, sends it to POST /api/extract, and displays the recovered MIR
 * in a clean verification panel.
 *
 * States:
 *   idle    → "Verify Embedded Media" button
 *   loading → animated spinner with pipeline step labels
 *   success → full recovered MIR display
 *   error   → error message with retry
 */

import { useState } from "react";
import {
  ShieldCheck,
  Loader2,
  AlertCircle,
  Hash,
  Clock,
  Cpu,
  Layers,
  Tag,
  Globe,
  Zap,
} from "lucide-react";
import { extractProvenance } from "../services/api";

/* ── MIR field row ────────────────────────────────────── */
function MIRRow({ icon: Icon, label, value, mono = false, accent = false }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-white/[0.04] last:border-0">
      <div className="w-7 h-7 rounded-lg bg-cyan-400/[0.08] border border-cyan-400/20 flex items-center justify-center shrink-0 mt-0.5">
        <Icon className="w-3.5 h-3.5 text-cyan-300" strokeWidth={1.8} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-0.5">
          {label}
        </p>
        <p
          className={`text-sm break-all leading-snug ${
            mono ? "font-mono text-cyan-200" : "font-medium text-slate-200"
          } ${accent ? "text-emerald-400" : ""}`}
        >
          {value}
        </p>
      </div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────── */
export default function VerifyPanel({ downloadUrl }) {
  const [phase, setPhase]   = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError]   = useState("");

  const handleVerify = async () => {
    setPhase("loading");
    setError("");
    try {
      const data = await extractProvenance(downloadUrl);
      setResult(data);
      setPhase("success");
    } catch (err) {
      const detail =
        err.response?.data?.detail ??
        err.message ??
        "Extraction failed. Please try again.";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setPhase("error");
    }
  };

  return (
    <div className="space-y-4">
      {/* Divider with label */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-white/[0.04]" />
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-widest px-2">
          Sprint 3 · Provenance Extraction
        </span>
        <div className="flex-1 h-px bg-white/[0.04]" />
      </div>

      {/* ── Idle ── */}
      {phase === "idle" && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500 text-center leading-relaxed">
            Read the LSB bitstream, decode the payload, and recover the
            Media Identity Record embedded in the image.
          </p>
          <button
            id="verify-btn"
            onClick={handleVerify}
            className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl
                       border border-cyan-400/30 bg-cyan-400/[0.08] hover:bg-cyan-400/[0.14]
                       text-cyan-200 hover:text-cyan-100 font-semibold text-sm tracking-wide
                       transition-all duration-200 ease-out
                       focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
          >
            <ShieldCheck className="w-5 h-5" />
            Verify Embedded Media
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {phase === "loading" && (
        <div className="flex flex-col items-center gap-3 py-5">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-cyan-400/20" />
            <div className="absolute inset-0 rounded-full border-2 border-t-cyan-300 animate-spin" />
            <div className="absolute inset-1 rounded-full bg-cyan-400/[0.08] flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-cyan-300" />
            </div>
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm font-medium text-slate-300">Extracting provenance…</p>
            <p className="text-xs text-slate-600">
              Reading LSBs → decoding bits → deserialising MIR
            </p>
          </div>
        </div>
      )}

      {/* ── Success ── */}
      {phase === "success" && result && (
        <div className="animate-slide-up space-y-4">
          {/* Header badge */}
          <div className="flex items-center gap-3 p-3.5 rounded-xl bg-cyan-400/[0.08] border border-cyan-400/20">
            <div className="w-8 h-8 rounded-lg bg-cyan-400/[0.12] border border-cyan-400/30 flex items-center justify-center shrink-0">
              <ShieldCheck className="w-4 h-4 text-cyan-300" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-sm font-semibold text-cyan-200">
                Provenance Verified
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Strategy:{" "}
                <span className="font-mono text-slate-400">
                  {result.strategy_used}
                </span>
              </p>
            </div>
            <div className="ml-auto flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-emerald-400 text-[10px] font-semibold uppercase tracking-wider">
                Authentic
              </span>
            </div>
          </div>

          {/* Recovered MIR */}
          <div className="bg-surface-900/60 border border-white/[0.05] rounded-xl px-4 py-1">
            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest pt-3 pb-1">
              Recovered Media Identity Record
            </p>
            <MIRRow
              icon={Hash}
              label="Media ID"
              value={result.mir.media_id}
              mono
            />
            <MIRRow
              icon={Cpu}
              label="AI Model"
              value={result.mir.model_name}
            />
            <MIRRow
              icon={Clock}
              label="Embedded Timestamp (UTC)"
              value={new Date(result.mir.timestamp).toLocaleString("en-GB", {
                timeZone: "UTC",
                dateStyle: "long",
                timeStyle: "long",
              })}
            />
            <MIRRow
              icon={Layers}
              label="Media Type"
              value={result.mir.media_type}
            />
            <MIRRow
              icon={Tag}
              label="MIR Version"
              value={result.mir.mir_version}
            />
            <MIRRow
              icon={Globe}
              label="Framework"
              value={result.mir.framework}
              accent
            />
          </div>

          {/* Re-verify */}
          <button
            onClick={handleVerify}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl
                       border border-white/[0.06] hover:border-cyan-400/20
                       text-slate-500 hover:text-cyan-300 text-xs font-medium
                       transition-all duration-200"
          >
            <Zap className="w-3 h-3" />
            Re-verify
          </button>
        </div>
      )}

      {/* ── Error ── */}
      {phase === "error" && (
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-300 leading-relaxed">{error}</p>
          </div>
          <button
            onClick={handleVerify}
            className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl
                       border border-cyan-400/30 bg-cyan-400/[0.08] hover:bg-cyan-400/[0.14]
                       text-cyan-200 font-semibold text-sm transition-all duration-200"
          >
            <ShieldCheck className="w-4 h-4" />
            Retry Verification
          </button>
        </div>
      )}
    </div>
  );
}
