/**
 * EmbedPanel — Sprint 2 UI component.
 *
 * Shown after successful registration. Allows the user to trigger
 * provenance embedding and then download the embedded PNG.
 * Sprint 3: once embedding succeeds, VerifyPanel is rendered below
 * so the user can immediately verify the recovered MIR.
 *
 * States:
 *   idle    → "Embed Provenance" button
 *   loading → spinner
 *   success → bit count + download button + VerifyPanel
 *   error   → error message + retry
 */

import { useState } from "react";
import {
  Fingerprint,
  AlertCircle,
  Download,
  CheckCircle2,
  Binary,
} from "lucide-react";
import { embedMedia } from "../services/api";
import VerifyPanel from "./VerifyPanel";

/* ── Bit counter pill ─────────────────────────────────── */
function BitBadge({ bits }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-400/[0.08] border border-cyan-400/20">
      <Binary className="w-4 h-4 text-cyan-300 shrink-0" strokeWidth={1.8} />
      <div>
        <p className="text-xs text-slate-500">Embedded Bits</p>
        <p className="text-sm font-mono font-semibold text-cyan-200">
          {bits.toLocaleString()} bits
          <span className="text-slate-600 ml-1">
            ({Math.ceil(bits / 8)} bytes)
          </span>
        </p>
      </div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────── */
export default function EmbedPanel({ imageId }) {
  const [phase, setPhase] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleEmbed = async () => {
    setPhase("loading");
    setError("");
    try {
      const data = await embedMedia(imageId);
      setResult(data);
      setPhase("success");
    } catch (err) {
      const detail =
        err.response?.data?.detail ??
        err.message ??
        "Embedding failed. Please try again.";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setPhase("error");
    }
  };

  // Construct the full URL: the Vite proxy rewrites /uploads/* → backend
  const downloadUrl =
    result?.embedded_image
      ? `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}${result.embedded_image}`
      : null;

  const handleDownload = async (e) => {
    e.preventDefault();
    if (!downloadUrl) return;
    try {
      const response = await fetch(downloadUrl);
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = "embedded_image.png";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Failed to download image:", err);
    }
  };

  return (
    <div className="space-y-4">
      {/* Divider with label */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-white/[0.05]" />
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-widest px-2">
          Sprint 2 · Provenance Embedding
        </span>
        <div className="flex-1 h-px bg-white/[0.05]" />
      </div>

      {/* ── Idle state ── */}
      {phase === "idle" && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500 text-center leading-relaxed">
            Embed the Media Identity Record (MIR) into the image using
            sequential LSB steganography. The result is visually identical
            to the original.
          </p>
          <button
            id="embed-btn"
            onClick={handleEmbed}
            className="btn-primary w-full"
          >
            <Fingerprint className="w-5 h-5" />
            Embed Provenance
          </button>
        </div>
      )}

      {/* ── Loading state ── */}
      {phase === "loading" && (
        <div className="flex flex-col items-center gap-3 py-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-cyan-400/20" />
            <div className="absolute inset-0 rounded-full border-2 border-t-cyan-300 animate-spin" />
            <div className="absolute inset-1 rounded-full bg-cyan-400/[0.08] flex items-center justify-center">
              <Fingerprint className="w-4 h-4 text-cyan-300" />
            </div>
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-slate-300">
              Embedding provenance…
            </p>
            <p className="text-xs text-slate-600 mt-0.5">
              Serialising MIR → encoding bits → LSB embedding
            </p>
          </div>
        </div>
      )}

      {/* ── Success state ── */}
      {phase === "success" && result && (
        <div className="animate-slide-up space-y-4">
          {/* Success header */}
          <div className="flex items-center gap-3 p-3.5 rounded-xl bg-cyan-400/[0.08] border border-cyan-400/20">
            <div className="w-8 h-8 rounded-lg bg-cyan-400/[0.12] border border-cyan-400/30 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-4 h-4 text-cyan-300" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-sm font-semibold text-cyan-200">
                Provenance Embedded Successfully
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                MIR written using sequential LSB steganography
              </p>
            </div>
          </div>

          {/* Bit count */}
          <BitBadge bits={result.embedded_bits} />

          {/* Download */}
          <button
            onClick={handleDownload}
            id="download-embedded-btn"
            className="btn-primary w-full"
          >
            <Download className="w-4 h-4" />
            Download Embedded Image
          </button>

          {/* Sprint 3 — Provenance extraction + verification */}
          <VerifyPanel downloadUrl={downloadUrl} />
        </div>
      )}

      {/* ── Error state ── */}
      {phase === "error" && (
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-300 leading-relaxed">{error}</p>
          </div>
          <button
            onClick={handleEmbed}
            className="btn-primary w-full"
          >
            <Fingerprint className="w-4 h-4" />
            Retry Embedding
          </button>
        </div>
      )}
    </div>
  );
}
