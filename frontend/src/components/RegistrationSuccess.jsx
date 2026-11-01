/**
 * RegistrationSuccess — displays provenance metadata after a successful registration.
 * Sprint 2: also renders EmbedPanel so the user can immediately embed the MIR.
 */

import { CheckCircle2, Hash, Clock, Cpu, Layers, RefreshCw } from "lucide-react";
import EmbedPanel from "./EmbedPanel";

function MetaRow({ icon: Icon, label, value, mono }) {
  return (
    <div className="meta-row">
      <div className="w-8 h-8 rounded-lg bg-brand-600/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
        <Icon className="w-4 h-4 text-brand-400" strokeWidth={1.8} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 mb-0.5">{label}</p>
        <p className={`text-sm text-slate-100 break-all ${mono ? "font-mono" : "font-medium"}`}>
          {value}
        </p>
      </div>
    </div>
  );
}

export default function RegistrationSuccess({ metadata, onReset }) {
  return (
    <div className="animate-slide-up space-y-6">
      {/* Header */}
      <div className="flex flex-col items-center gap-3 py-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" strokeWidth={1.5} />
          </div>
          {/* Glow ring */}
          <div className="absolute inset-0 rounded-2xl bg-emerald-500/10 blur-xl -z-10 scale-150" />
        </div>
        <div className="text-center">
          <h3 className="text-xl font-bold text-slate-100">Registration Successful</h3>
          <p className="text-sm text-slate-500 mt-1">
            Provenance metadata has been recorded in the Aletheia registry.
          </p>
        </div>
      </div>

      {/* Metadata card — Sprint 1 (unchanged) */}
      <div className="glass-card px-5 py-1 divide-y divide-white/[0.05]">
        <MetaRow
          icon={Hash}
          label="Image ID"
          value={metadata.image_id}
          mono
        />
        <MetaRow
          icon={Clock}
          label="Timestamp (UTC)"
          value={new Date(metadata.timestamp).toLocaleString("en-GB", {
            timeZone: "UTC",
            dateStyle: "long",
            timeStyle: "long",
          })}
        />
        <MetaRow
          icon={Cpu}
          label="AI Model"
          value={metadata.model_name}
        />
        <MetaRow
          icon={Layers}
          label="Media Type"
          value={metadata.media_type}
        />
        <MetaRow
          icon={CheckCircle2}
          label="Framework Version"
          value={`Aletheia v${metadata.framework_version}`}
        />
      </div>

      {/* Sprint 2 — Provenance Embedding panel */}
      <EmbedPanel imageId={metadata.image_id} />

      {/* Reset */}
      <button onClick={onReset} className="btn-primary w-full">
        <RefreshCw className="w-4 h-4" />
        Register Another Image
      </button>
    </div>
  );
}
