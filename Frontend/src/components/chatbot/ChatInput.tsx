import React, { useState, useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isGenerating: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, onStop, isGenerating }) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (isGenerating) {
      onStop();
      return;
    }
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize input height based on text lines
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  return (
    <div className="flex gap-2 p-3 border-t border-border bg-card/60 backdrop-blur-md">
      <div className="relative flex-1 flex items-center min-w-0">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isGenerating ? "Analyzing data streams..." : "Ask Praecantator AI..."}
          disabled={false} // Textarea remains active so users can copy or prepare next prompt
          rows={1}
          className="w-full pl-3 pr-10 py-2.5 rounded-lg border border-border bg-muted/40 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-hidden focus:border-red-500/50 resize-none font-sans min-h-[38px] max-h-[120px] custom-scrollbar leading-relaxed"
        />
        
        {/* Toggle between Send and Stop Generation inside the input area */}
        {isGenerating ? (
          <button
            onClick={onStop}
            className="absolute right-2 p-1.5 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-500 transition-colors cursor-pointer"
            title="Stop generation"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!text.trim()}
            className={`absolute right-2 p-1.5 rounded-md transition-colors cursor-pointer ${
              text.trim()
                ? "bg-red-500 text-white hover:bg-red-600 shadow-sm"
                : "text-muted-foreground/40 bg-transparent"
            }`}
            title="Send query"
          >
            <Send size={13} />
          </button>
        )}
      </div>
    </div>
  );
};
