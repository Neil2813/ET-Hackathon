import React, { useEffect, useRef } from "react";
import { Bot, AlertTriangle } from "lucide-react";
import { CopilotMessage } from "./services/copilotApi";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

interface ChatWindowProps {
  messages: CopilotMessage[];
  isGenerating: boolean;
  error: string | null;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isGenerating, error }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isGenerating]);

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 custom-scrollbar bg-card/[0.15]"
    >
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center select-none">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/25 flex items-center justify-center mb-4 text-red-500 animate-pulse">
            <Bot size={22} />
          </div>
          <h3 className="text-xs font-headline font-bold text-foreground uppercase tracking-widest mb-1.5">
            Operational Intelligence Copilot
          </h3>
          <p className="text-[11px] text-muted-foreground max-w-xs leading-relaxed font-sans">
            Ready to analyze platform metrics, investigate supply chain network exposures, explain routing alternatives, and brief you on governance checkpoint statuses.
          </p>
        </div>
      ) : (
        messages.map((msg, idx) => (
          // Renders typing indicator for the very last assistant message if it is currently generating
          <MessageBubble key={idx} message={msg} />
        ))
      )}

      {isGenerating && messages.length > 0 && messages[messages.length - 1].content === "" && (
        <TypingIndicator />
      )}

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-lg border border-red-500/20 bg-red-500/[0.02] text-red-400 text-xs font-sans">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <div className="flex-1 leading-normal font-medium">{error}</div>
        </div>
      )}
    </div>
  );
};
