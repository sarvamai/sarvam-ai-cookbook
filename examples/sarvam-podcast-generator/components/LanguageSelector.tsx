'use client';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Globe, Languages } from 'lucide-react';

interface LanguageSelectorProps {
  selectedLanguage: string;
  onLanguageChange: (language: string) => void;
}

const languages = [
  { value: 'hi-IN', label: 'Hindi (हिंदी)', flag: '🇮🇳', region: 'India' },
  { value: 'en-IN', label: 'English (Indian)', flag: '🇮🇳', region: 'India' },
  { value: 'ta-IN', label: 'Tamil (தமிழ்)', flag: '🇮🇳', region: 'India' },
  { value: 'te-IN', label: 'Telugu (తెలుగు)', flag: '🇮🇳', region: 'India' },
  { value: 'kn-IN', label: 'Kannada (ಕನ್ನಡ)', flag: '🇮🇳', region: 'India' },
  { value: 'ml-IN', label: 'Malayalam (മലയാളം)', flag: '🇮🇳', region: 'India' },
  { value: 'bn-IN', label: 'Bengali (বাংলা)', flag: '🇮🇳', region: 'India' },
  { value: 'gu-IN', label: 'Gujarati (ગુજરાતી)', flag: '🇮🇳', region: 'India' },
  { value: 'mr-IN', label: 'Marathi (मराठी)', flag: '🇮🇳', region: 'India' },
  { value: 'pa-IN', label: 'Punjabi (ਪੰਜਾਬੀ)', flag: '🇮🇳', region: 'India' },
  { value: 'od-IN', label: 'Odia (ଓଡ଼ିଆ)', flag: '🇮🇳', region: 'India' }
];

export function LanguageSelector({ selectedLanguage, onLanguageChange }: LanguageSelectorProps) {
  const selectedLang = languages.find(lang => lang.value === selectedLanguage);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Label htmlFor="language-select" className="text-sm font-medium flex items-center gap-2">
          <Languages className="h-4 w-4" />
          Podcast Language
        </Label>
        <Badge variant="secondary" className="text-xs">
          <Globe className="h-3 w-3 mr-1" />
          Multi-language support
        </Badge>
      </div>
      
      <Select value={selectedLanguage} onValueChange={onLanguageChange}>
        <SelectTrigger id="language-select" className="w-full">
          <SelectValue>
            {selectedLang && (
              <div className="flex items-center gap-2">
                <span className="text-lg">{selectedLang.flag}</span>
                <span className="font-medium">{selectedLang.label}</span>
                <Badge variant="outline" className="text-xs ml-auto">
                  {selectedLang.region}
                </Badge>
              </div>
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <div className="px-2 py-1.5">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
              Available Languages
            </p>
          </div>
          {languages.map((language) => (
            <SelectItem key={language.value} value={language.value} className="cursor-pointer">
              <div className="flex items-center gap-3 w-full">
                <span className="text-lg">{language.flag}</span>
                <div className="flex-1">
                  <div className="font-medium">{language.label}</div>
                  <div className="text-xs text-muted-foreground">{language.region}</div>
                </div>
                {language.value === selectedLanguage && (
                  <Badge variant="default" className="text-xs">
                    Selected
                  </Badge>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      
      <div className="text-xs text-muted-foreground">
        Select your preferred language for podcast generation. All languages are supported by Sarvam AI's multilingual models.
      </div>
    </div>
  );
} 