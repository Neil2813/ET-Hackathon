import React from "react";
import { Sparkles } from "lucide-react";

interface SuggestionChipsProps {
  suggestions: string[];
  onSelectSuggestion: (text: string) => void;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  onSelectSuggestion,
}) => {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 p-3 border-t border-border bg-card/40 backdrop-blur-xs">
      <div className="flex items-center gap-1 text-[10px] uppercase font-mono tracking-wider text-muted-foreground font-semibold px-1">
        <Sparkles size={10} className="text-red-500" /> Suggested Actions
      </div>
      <div className="flex flex-wrap gap-1.5 overflow-x-auto py-0.5 max-h-24 custom-scrollbar">
        {suggestions.map((text, idx) => (
          <button
            key={idx}
            onClick={() => onSelectSuggestion(text)}
            className="px-2.5 py-1.5 rounded-full text-xs font-medium bg-muted/60 border border-border hover:border-red-500/40 hover:bg-red-500/[0.04] text-foreground hover:text-red-400 transition-all duration-200 shadow-sm cursor-pointer whitespace-nowrap"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
};
