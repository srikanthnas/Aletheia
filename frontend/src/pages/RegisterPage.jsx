import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Image as ImageIcon, Loader2, ShieldPlus } from "lucide-react";
import UploadZone from "../components/UploadZone";
import ModelSelector from "../components/ModelSelector";
import RegistrationSuccess from "../components/RegistrationSuccess";
import { registerMedia } from "../services/api";

export default function RegisterPage() {
  const [file, setFile] = useState(null);
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  useEffect(() => {
    if (!file) { setPreviewUrl(null); return undefined; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleRegister = async () => {
    if (!file || !model || loading) return;
    setLoading(true);
    setError("");
    try {
      const data = await registerMedia(file, model);
      setResult(data.metadata);
    } catch (err) {
      const detail = err.response?.data?.detail ?? err.message ?? "Registration failed.";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally { setLoading(false); }
  };

  const handleReset = () => { setFile(null); setModel(""); setError(""); setResult(null); };

  return <main className="page-shell"><div className="page-heading"><div><p className="eyebrow">Image provenance</p><h1>Register Image</h1><p>Register an image, then embed a verifiable Media Identity Record into it.</p></div><span className="workflow-heading-status"><CheckCircle2 className="h-4 w-4" /> LSB embedding pipeline</span></div>{result ? <section className="registration-result-shell"><RegistrationSuccess metadata={result} onReset={handleReset} /></section> : <section className="media-workspace"><div className="media-column"><div className="media-preview">{previewUrl ? <img src={previewUrl} alt="Image selected for registration" className="h-full w-full object-contain" /> : <div className="media-placeholder"><ImageIcon className="h-9 w-9" /><span>Image preview</span><small>Select an image to preview it here</small></div>}</div>{file && <div className="file-strip"><span className="truncate">{file.name}</span><span>{(file.size / 1024).toFixed(1)} KB</span></div>}</div><div className="workflow-panel"><div><h2>Embed image provenance</h2><p className="panel-copy">Choose the source model, register the media, and continue into the existing embedding and extraction steps.</p></div><UploadZone file={file} onFile={(next) => { setFile(next); setError(""); }} /><ModelSelector value={model} onChange={setModel} />{error && <div className="error-banner"><AlertCircle className="mr-2 inline h-4 w-4" />{error}</div>}<button id="register-btn" onClick={handleRegister} disabled={!file || !model || loading} className="btn-primary w-full">{loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Registering image…</> : <><ShieldPlus className="h-4 w-4" /> Register & continue to embed</>}</button>{(!file || !model) && <p className="text-center text-xs text-slate-600">Upload an image and select its source model to continue.</p>}</div></section>}</main>;
}
