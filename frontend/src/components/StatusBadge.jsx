import { AlertTriangle, CheckCircle2, CircleX, Clock3, HelpCircle, ShieldAlert } from "lucide-react";

const STATUS = {
  AUTHENTIC: { label: "Verified", icon: CheckCircle2, className: "status-good", detail: "The provenance record and integrity checks are consistent." },
  VERIFIED: { label: "Verified", icon: CheckCircle2, className: "status-good", detail: "The provenance record was successfully extracted and validated." },
  "MINOR MODIFICATION": { label: "Partially verified", icon: ShieldAlert, className: "status-warn", detail: "Provenance was recovered, but the integrity analysis found changes." },
  MODIFIED: { label: "Modified", icon: AlertTriangle, className: "status-warn", detail: "The media was identified, but its content differs from the registered reference." },
  TAMPERED: { label: "Tampered", icon: CircleX, className: "status-danger", detail: "The integrity analysis indicates significant changes." },
  UNVERIFIED: { label: "No provenance", icon: HelpCircle, className: "status-neutral", detail: "No valid provenance result was returned for this media." },
  "NO PROVENANCE": { label: "No provenance", icon: HelpCircle, className: "status-neutral", detail: "No valid provenance record was detected." },
  PROCESSING: { label: "Processing", icon: Clock3, className: "status-info", detail: "The media analysis is still running." },
};

export function getStatusConfig(value) {
  return STATUS[String(value ?? "UNVERIFIED").toUpperCase()] ?? STATUS.UNVERIFIED;
}

export default function StatusBadge({ value, compact = false }) {
  const config = getStatusConfig(value);
  const Icon = config.icon;
  return <span className={`status-badge ${config.className} ${compact ? "status-compact" : ""}`}><Icon className="h-3.5 w-3.5" />{config.label}</span>;
}
