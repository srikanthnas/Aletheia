/**
 * AnalyzePage.jsx — Full End-to-End Aletheia Assessment Page (Layer 3).
 *
 * Workflow:
 *   1. User uploads an image (any format).
 *   2. assessMedia() calls POST /api/assess.
 *   3. The full three-layer pipeline runs server-side.
 *   4. TrustScoreCard displays the verdict and trust score.
 *   5. ForensicsBreakdown shows per-detector results and evidence.
 *
 * Design:
 *   - Tab-based results view (Overview / Forensics) to manage information density.
 *   - Animated loading state with pipeline stage indicators.
 *   - All three layers are clearly labeled in the results.
 */

import { useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  ScanSearch,
  Loader2,
  AlertCircle,
  RefreshCw,
  FileImage,
  ShieldCheck,
  Cpu,
  Brain,
} from "lucide-react";
import TrustScoreCard from "../components/TrustScoreCard";
import ForensicsBreakdown from "../components/ForensicsBreakdown";
import { assessMedia } from "../services/api";

/* ── Pipeline stage display during loading ─────────────────────────── */
const PIPELINE_STAGES = [
  { icon: Cpu,        label: "Running AI Forensics Engine…",        detail: "CLIP + Statistical + Artifact + Frequency" },
  { icon: ShieldCheck, label: "Attempting Provenance Extraction…",   detail: "Multi-region ADPE watermark analysis" },
  { icon: Brain,      label: "Trust & Decision Engine reasoning…",  detail: "Rule-based evidence fusion" },
];

function LoadingState() {
  const [stage, setStage] = useState(0);

  // Cycle through stages for UX (timing is cosmetic — server is doing real work)
  useEffect(() => {
    const timers = [
      setTimeout(() => setStage(1), 2500),
      setTimeout(() => setStage(2), 6000),
    ];
    return () => timers.forEach(clearTimeout);
  });

  const s = PIPELINE_STAGES[stage];
  const StageIcon = s.icon;

  return (
    <div className="flex flex-col items-center justify-center gap-5 py-12">
      <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-2xl bg-cyan-400/[0.08] border border-cyan-400/20 flex items-center justify-center">
          <StageIcon className="w-7 h-7 text-cyan-300" strokeWidth={1.5} />
        </div>
        <div className="absolute -inset-1 rounded-3xl border border-cyan-400/20 animate-ping opacity-20" />
      </div>

      <div className="text-center space-y-1.5">
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 text-cyan-300 animate-spin" />
          <p className="text-sm font-semibold text-slate-200">{s.label}</p>
        </div>
        <p className="text-xs text-slate-500">{s.detail}</p>
      </div>

      {/* Stage dots */}
      <div className="flex gap-2">
        {PIPELINE_STAGES.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all duration-500 ${
              i <= stage ? "bg-cyan-300" : "bg-white/10"
            }`}
          />
        ))}
      </div>

      <p className="text-xs text-slate-600">
        Full pipeline may take 10–30 seconds (CLIP inference)
      </p>
    </div>
  );
}

/* ── Drop zone ─────────────────────────────────────────────────────── */
function AnalyzeDropZone({ file, onFile }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const accept = (f) => {
    if (f && f.type.startsWith("image/")) onFile(f);
  };

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); accept(e.dataTransfer.files[0]); }}
      className={`relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
        cursor-pointer transition-all duration-200 py-10 px-6
        ${dragging
          ? "border-cyan-400 bg-cyan-400/[0.08]"
          : file
          ? "border-cyan-400/40 bg-cyan-400/[0.05]"
          : "border-white/10 hover:border-white/20 bg-white/[0.02] hover:bg-white/[0.04]"
        }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => accept(e.target.files?.[0])}
      />

      {file ? (
        <>
          <div className="w-12 h-12 rounded-xl bg-cyan-400/[0.08] border border-cyan-400/20 flex items-center justify-center">
            <FileImage className="w-6 h-6 text-cyan-300" strokeWidth={1.5} />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-200">{file.name}</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {(file.size / 1024).toFixed(1)} KB — click to change
            </p>
          </div>
        </>
      ) : (
        <>
          <div className="w-12 h-12 rounded-xl bg-cyan-400/[0.08] border border-cyan-400/20 flex items-center justify-center">
            <ScanSearch className="w-6 h-6 text-cyan-300" strokeWidth={1.5} />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-300">Drop any image here</p>
            <p className="text-xs text-slate-500 mt-0.5">
              PNG recommended for Aletheia-embedded images · Any format for forensics-only
            </p>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Results tabs ──────────────────────────────────────────────────── */
const RESULT_TABS = [
  { id: "overview",   label: "Trust Assessment" },
  { id: "forensics",  label: "Forensics Detail" },
];

function ResultsTabs({ active, onSelect }) {
  return (
    <div className="flex gap-1 p-1 rounded-xl bg-white/[0.03] border border-white/[0.05]">
      {RESULT_TABS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onSelect(id)}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all duration-200 ${
            active === id
              ? "bg-white/[0.08] border border-white/[0.10] text-slate-100"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────────── */
export default function AnalyzePage() {
  const [file,    setFile]    = useState(null);
  const [phase,   setPhase]   = useState("idle");   // idle | loading | success | error
  const [report,  setReport]  = useState(null);
  const [error,   setError]   = useState("");
  const [tab,     setTab]     = useState("overview");

  const handleAnalyze = async () => {
    if (!file) return;
    setPhase("loading");
    setError("");
    setTab("overview");

    try {
      const data = await assessMedia(file);
      setReport(data);
      setPhase("success");
    } catch (err) {
      const detail = err.response?.data?.detail ?? err.message ?? "Analysis failed.";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setPhase("error");
    }
  };

  const handleReset = () => {
    setFile(null);
    setPhase("idle");
    setReport(null);
    setError("");
    setTab("overview");
  };

  return (
    <main className="page-shell">

      {/* ── Page header ── */}
      <section className="page-heading">
        <div>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-400/[0.08] border border-cyan-400/20 mb-4">
          <ScanSearch className="w-3.5 h-3.5 text-cyan-300" />
          <span className="text-cyan-300 text-xs font-semibold tracking-widest uppercase">
            Layer 3 · Trust & Decision Engine
          </span>
        </div>

        <h1>Full Media Analysis</h1>

        <p>Active provenance, passive forensics and trust fusion.</p>

        <p className="mt-3 max-w-xl mx-auto text-sm text-slate-600 leading-relaxed">
          Upload any image. The complete three-layer pipeline runs:
          AI Forensics (CLIP, Statistical, Artifact, Frequency) ·
          Provenance Extraction & Verification ·
          Trust & Decision Engine fusion.
        </p>

        {/* Pipeline diagram */}
        <div className="mt-6 flex items-center justify-center gap-1.5 flex-wrap text-[10px] font-bold text-slate-600 uppercase tracking-wider">
          {["AI Forensics", "→", "Provenance", "→", "Trust Engine", "→", "Final Verdict"].map((label, i) => (
            <span key={i} className={label === "→" ? "text-slate-700 mx-1" : "px-2 py-1 rounded-md bg-white/[0.03] border border-white/[0.06] text-slate-500"}>
              {label}
            </span>
          ))}
        </div>
        </div>
      </section>

      {/* ── Main content ── */}
      <section className="flex-1 flex items-start justify-center pb-16">
        {phase === "success" && report ? (
          /* Results view */
          <div className="w-full max-w-2xl space-y-4">

            {/* Tab switcher */}
            <ResultsTabs active={tab} onSelect={setTab} />

            {/* Tab content */}
            {tab === "overview"  && <TrustScoreCard  report={report} />}
            {tab === "forensics" && <ForensicsBreakdown report={report} />}

            {/* Reset button */}
            <button
              id="analyze-reset-btn"
              onClick={handleReset}
              className="btn-primary w-full mt-2"
            >
              <RefreshCw className="w-4 h-4" />
              Analyze Another Image
            </button>
          </div>
        ) : (
          /* Upload + action view */
          <div className="w-full max-w-2xl glass-card p-5 sm:p-8">

            {phase === "loading" ? (
              <LoadingState />
            ) : (
              <div className="space-y-6">
                <AnalyzeDropZone file={file} onFile={setFile} />

                {/* Error banner */}
                {phase === "error" && (
                  <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                    <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-sm text-red-300 leading-relaxed">{error}</p>
                  </div>
                )}

                {/* Analyze button */}
                <button
                  id="analyze-submit-btn"
                  onClick={handleAnalyze}
                  disabled={!file || phase === "loading"}
                  className="btn-primary w-full text-base py-3.5
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <ScanSearch className="w-5 h-5" />
                  Run Full Analysis
                </button>

                {!file && (
                  <p className="text-center text-xs text-slate-600">
                    Upload an image to begin the full three-layer analysis.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
