"use client";

import { LANGUAGES } from "@/lib/constants";
import type { LanguageCode } from "@/lib/types";

interface LanguageSelectorProps {
  value: LanguageCode;
  onChange: (lang: LanguageCode) => void;
  label?: string;
  id?: string;
  className?: string;
}

export function LanguageSelector({
  value,
  onChange,
  label = "Language",
  id = "language-select",
  className = "",
}: LanguageSelectorProps) {
  return (
    <div className={className}>
      <label
        htmlFor={id}
        className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5"
      >
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as LanguageCode)}
        className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-800
                   focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                   transition-colors cursor-pointer hover:border-slate-300"
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.flag} {lang.name} — {lang.nativeName}
          </option>
        ))}
      </select>
    </div>
  );
}
