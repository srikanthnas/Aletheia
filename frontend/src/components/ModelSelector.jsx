/**
 * ModelSelector — styled dropdown for selecting the generative AI model.
 */

import { Cpu } from "lucide-react";

const MODELS = [
  { value: "", label: "Select an AI model…", disabled: true },
  { value: "Stable Diffusion XL", label: "Stable Diffusion XL" },
  { value: "DALL-E",              label: "DALL-E" },
  { value: "Gemini",             label: "Gemini" },
  { value: "Flux",               label: "Flux" },
  { value: "Midjourney",         label: "Midjourney" },
  { value: "Other",              label: "Other" },
];

export default function ModelSelector({ value, onChange }) {
  return (
    <div className="space-y-2">
      <label htmlFor="model-select" className="label-text">
        AI Model Used
      </label>

      <div className="relative">
        <Cpu
          className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none"
          strokeWidth={1.8}
        />
        <select
          id="model-select"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="select-field pl-10"
        >
          {MODELS.map((m) => (
            <option
              key={m.value}
              value={m.value}
              disabled={m.disabled}
            >
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <p className="text-xs text-slate-600">
        In future versions this will be auto-populated from the integrated AI provider.
      </p>
    </div>
  );
}
