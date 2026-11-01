import { useRef, useState } from "react";
import { FileImage, FileVideo, UploadCloud, X } from "lucide-react";
import AletheiaLogo from "./AletheiaLogo";

export default function MediaUploader({ file, onFile, kind = "image", accept = "image/*", title, subtitle }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const Icon = kind === "video" ? FileVideo : FileImage;
  const choose = (nextFile) => { if (nextFile) onFile(nextFile); };
  const clear = (event) => { event.stopPropagation(); onFile(null); if (inputRef.current) inputRef.current.value = ""; };

  return <div className={`upload-zone ${dragging ? "upload-zone-active" : ""} ${file ? "upload-zone-filled" : ""}`} onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files?.[0]); }}>
    <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={(event) => choose(event.target.files?.[0])} />
    {file ? <><div className="upload-icon upload-icon-success"><Icon className="h-6 w-6" /></div><div className="min-w-0 text-center"><p className="truncate text-sm font-semibold text-orange-200">{file.name}</p><p className="mt-1 text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB · click to replace</p></div><button type="button" title="Remove file" onClick={clear} className="icon-button absolute right-3 top-3"><X className="h-4 w-4" /></button></> : <><AletheiaLogo /><div className="text-center"><p className="text-sm font-semibold text-orange-200">{title ?? `Drop your ${kind} here`}</p><p className="mt-1 text-xs text-slate-500">{subtitle ?? "or browse from your computer"}</p></div></>}
  </div>;
}
