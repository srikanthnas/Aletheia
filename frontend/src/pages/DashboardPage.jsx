import { ArrowRight, Image, ScanLine, ShieldCheck, Video } from "lucide-react";
import AletheiaLogo from "../components/AletheiaLogo";

const cards = [
  { id: "image-register", label: "Register & embed image", note: "Create a verifiable image provenance record.", icon: Image },
  { id: "video-register", label: "Register & embed video", note: "Protect temporal checkpoints across a video.", icon: Video },
  { id: "image-verify", label: "Verify image", note: "Recover provenance and inspect image integrity.", icon: ShieldCheck },
  { id: "video-verify", label: "Verify video", note: "Check temporal recovery and video integrity.", icon: ScanLine },
];

export default function DashboardPage({ onNavigate }) {
  return <main className="dashboard-landing"><section className="dashboard-stage"><div className="dashboard-map"><div className="map-fade" /><div className="reference-kicker"><AletheiaLogo compact /><span>ALETHEIA / GLOBAL MEDIA INTEGRITY</span></div></div><div className="dashboard-actions"><div className="dashboard-actions-heading"><div><p className="eyebrow">Aletheia workspace</p><h2>Media Integrity Tools</h2></div><span className="dashboard-command">SECURE CHANNEL / READY</span></div><div className="workflow-grid">{cards.map(({ id, label, note, icon: Icon }, index) => <button className="workflow-card" key={id} onClick={() => onNavigate(id)}><span className="workflow-index">0{index + 1}</span><span className="workflow-icon"><Icon className="h-5 w-5" /></span><span className="workflow-copy"><strong>{label}</strong><small>{note}</small></span><ArrowRight className="workflow-arrow h-4 w-4" /></button>)}</div></div></section></main>;
}
