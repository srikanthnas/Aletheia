import { useState } from "react";
import { ChevronDown } from "lucide-react";

export function DetailRow({ label, value, mono = false }) {
  if (value === undefined || value === null || value === "") return null;
  return <div className="detail-row"><span>{label}</span><strong className={mono ? "font-mono break-all" : ""}>{String(value)}</strong></div>;
}

export default function TechnicalDetails({ sections }) {
  return <div className="space-y-3">{sections.filter((section) => section.rows.some((row) => row.value !== undefined && row.value !== null && row.value !== "")).map((section) => <TechnicalSection key={section.title} {...section} />)}</div>;
}

function TechnicalSection({ title, rows }) {
  const [open, setOpen] = useState(false);
  const visible = rows.filter((row) => row.value !== undefined && row.value !== null && row.value !== "");
  return <section className="detail-section"><button onClick={() => setOpen((value) => !value)} className="detail-section-toggle"><span>{title}</span><ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} /></button>{open && <div className="px-4 pb-3">{visible.map((row) => <DetailRow key={row.label} {...row} />)}</div>}</section>;
}
