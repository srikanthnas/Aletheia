/**
 * UploadZone — drag-and-drop / click-to-browse image upload component.
 * Handles preview, file validation feedback, and clear action.
 */

import { useCallback, useRef, useState } from "react";
import { UploadCloud, X, ImageIcon } from "lucide-react";

const ALLOWED_TYPES = ["image/png", "image/jpeg"];
const MAX_SIZE_MB = 20;

export default function UploadZone({ file, onFile }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const validate = (f) => {
    if (!ALLOWED_TYPES.includes(f.type)) {
      setError("Only PNG, JPG, and JPEG files are accepted.");
      return false;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      return false;
    }
    setError("");
    return true;
  };

  const handleFile = useCallback(
    (f) => {
      if (f && validate(f)) onFile(f);
    },
    [onFile]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const onInputChange = (e) => {
    const f = e.target.files[0];
    if (f) handleFile(f);
  };

  const clearFile = (e) => {
    e.stopPropagation();
    onFile(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const previewUrl = file ? URL.createObjectURL(file) : null;

  return (
    <div className="space-y-2">
      <label className="label-text">Upload AI-Generated Image</label>

      <div
        onClick={() => !file && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`
          relative group flex flex-col items-center justify-center
          rounded-2xl border-2 border-dashed
          transition-all duration-300 overflow-hidden
          ${file ? "border-brand-500/40 cursor-default h-72" : "border-white/10 cursor-pointer h-52"}
          ${dragging ? "border-brand-400/70 bg-brand-500/10 scale-[1.01]" : "hover:border-white/20 hover:bg-white/[0.02]"}
          bg-surface-800/40
        `}
      >
        {file && previewUrl ? (
          <>
            <img
              src={previewUrl}
              alt="Preview"
              className="absolute inset-0 w-full h-full object-contain p-3"
            />
            {/* Overlay gradient */}
            <div className="absolute inset-0 bg-gradient-to-t from-surface-950/80 via-transparent to-transparent" />

            {/* File info strip */}
            <div className="absolute bottom-0 inset-x-0 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-brand-400 shrink-0" />
                <span className="text-xs text-slate-300 truncate max-w-[200px]">
                  {file.name}
                </span>
                <span className="badge bg-brand-500/20 text-brand-300">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
              </div>
              <button
                onClick={clearFile}
                className="w-7 h-7 rounded-full bg-surface-800/80 hover:bg-red-500/30 border border-white/10 flex items-center justify-center transition-colors"
                title="Remove image"
              >
                <X className="w-3.5 h-3.5 text-slate-300" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-3 p-6 text-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-600/10 border border-brand-500/20 flex items-center justify-center group-hover:bg-brand-600/20 transition-colors">
              <UploadCloud
                className={`w-7 h-7 transition-all duration-300 ${dragging ? "text-brand-300 scale-110" : "text-brand-500"}`}
                strokeWidth={1.5}
              />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">
                {dragging ? "Drop to upload" : "Drag & drop your image here"}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                or <span className="text-brand-400 underline-offset-2 underline">browse files</span>
                &nbsp;— PNG, JPG, JPEG · Max {MAX_SIZE_MB} MB
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 flex items-center gap-1.5 animate-fade-in">
          <span className="w-1 h-1 rounded-full bg-red-400 shrink-0" />
          {error}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg"
        className="hidden"
        onChange={onInputChange}
      />
    </div>
  );
}
