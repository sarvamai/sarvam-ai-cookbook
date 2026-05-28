"use client";

import { ChevronDown } from "lucide-react";
import { LANGUAGES } from "@/lib/constants";
import type { LanguageCode } from "@/lib/types";

interface LanguageSelectorProps {
  value:     LanguageCode;
  onChange:  (lang: LanguageCode) => void;
  id?:       string;
  className?: string;
}

export function LanguageSelector({
  value,
  onChange,
  id        = "language-select",
  className = "",
}: LanguageSelectorProps) {
  return (
    <div className={`relative inline-flex items-center ${className}`}>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as LanguageCode)}
        className="appearance-none pl-4 pr-9 py-2 bg-white border border-slate-200 rounded-full
                   text-sm font-medium text-slate-700 cursor-pointer
                   focus:outline-none focus:ring-2 focus:ring-indigo-200
                   hover:border-slate-300 transition-colors"
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.name} — {lang.nativeName}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 w-3.5 h-3.5 text-slate-400" />
    </div>
  );
}
