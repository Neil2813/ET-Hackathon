import React, { useEffect, useRef } from "react";
import { Bot, AlertTriangle, RefreshCw } from "lucide-react";
import { CopilotMessage } from "./services/chatbotApi";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

interface ChatWindowProps {
  messages: CopilotMessage[];
  isGenerating: boolean;
  error: string | null;
  onRetry?: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isGenerating, error, onRetry }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation on new messages or while generating
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isGenerating]);

  // Show typing indicator when:
  // - generation is active AND
  // - the last message is an assistant placeholder with little or no content yet
  const lastMsg = messages[messages.length - 1];
  const showTypingIndicator =
    isGenerating &&
    messages.length > 0 &&
    lastMsg?.role === "assistant" &&
    (lastMsg.content ?? "").length < 5;

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
          <MessageBubble key={idx} message={msg} />
        ))
      )}

      {showTypingIndicator && <TypingIndicator />}

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-lg border border-red-500/20 bg-red-500/[0.04] text-red-400 text-xs font-sans">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <div className="flex-1 leading-normal font-medium">{error}</div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors cursor-pointer text-[10px] font-semibold uppercase tracking-wider"
              title="Retry last message"
            >
              <RefreshCw size={10} />
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
};
