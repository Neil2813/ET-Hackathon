import React from "react";

export const TypingIndicator: React.FC = () => {
  return (
    <div className="flex items-center gap-1.5 p-3 rounded-lg bg-muted/40 border border-border w-fit max-w-[85%] select-none">
      <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce [animation-delay:-0.3s]" />
      <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce [animation-delay:-0.15s]" />
      <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce" />
      <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest pl-1.5">
        Analyzing Context
      </span>
    </div>
  );
};
