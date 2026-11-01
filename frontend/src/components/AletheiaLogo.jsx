import { useEffect, useState } from "react";
import { BrainCircuit, Hexagon, ShieldCheck } from "lucide-react";

const FRAMES = [
  { Icon: BrainCircuit, label: "AI signal" },
  { Icon: ShieldCheck, label: "Security signal" },
  { Icon: Hexagon, label: "Aletheia signal" },
];

export default function AletheiaLogo({ compact = false, watermark = false }) {
  const [frame, setFrame] = useState(0);
  const current = FRAMES[frame];
  const Icon = current.Icon;

  useEffect(() => {
    const timer = window.setInterval(() => setFrame((value) => (value + 1) % FRAMES.length), 2400);
    return () => window.clearInterval(timer);
  }, []);

  return <div className={`aletheia-logo ${compact ? "aletheia-logo-compact" : ""} ${watermark ? "aletheia-logo-watermark" : ""}`} title={current.label} aria-label={current.label}>
    <div className="aletheia-logo-orbit" />
    <div className="aletheia-logo-core"><Icon key={current.label} className="aletheia-logo-icon" /></div>
    {!compact && <span className="aletheia-logo-caption">ALETHEIA // {current.label.toUpperCase()}</span>}
  </div>;
}
