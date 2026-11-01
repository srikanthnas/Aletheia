/**
 * App.jsx — root component.
 *
 * Sprint 4: adds tab-based navigation.
 *   "Register & Embed" → RegisterPage (Sprints 1-3)
 *   "Verify Media"     → VerifyPage   (Sprint 4)
 *   "Analyze"          → AnalyzePage  (Layer 3 — full pipeline)
 *
 * Uses local state (no router dependency) — the app is single-page.
 */

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import DashboardPage from "./pages/DashboardPage";
import RegisterPage from "./pages/RegisterPage";
import VerifyPage from "./pages/VerifyPage";
import VideoPage from "./pages/VideoPage";

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");

  return (
    <div className="app-root min-h-screen flex flex-col">
      <div className="security-globe-background" aria-hidden="true" />
      <div className="app-content">{activeTab !== "dashboard" && <button className="back-dashboard" onClick={() => setActiveTab("dashboard")}><ArrowLeft className="h-4 w-4" /> Dashboard</button>}{activeTab === "dashboard" ? <DashboardPage onNavigate={setActiveTab} /> :
       activeTab === "image-register" ? <RegisterPage /> :
       activeTab === "video-register" ? <VideoPage workflow="register" /> :
       activeTab === "image-verify" ? <VerifyPage /> :
       <VideoPage workflow="verify" />}</div>
    </div>
  );
}
