import React, { useState } from "react";
import { Copy, Check, Bot, User, Clock } from "lucide-react";
import { CopilotMessage } from "./services/copilotApi";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface MessageBubbleProps {
  message: CopilotMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const { role, content, timestamp } = message;
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy message:", err);
    }
  };

  // Dynamically infer agent/expert mode based on content keywords
  const inferAnalystMode = (text: string): string => {
    const lower = text.toLowerCase();
    if (lower.includes("briefing") || lower.includes("executive summary") || lower.includes("brief")) {
      return "Executive Advisor";
    }
    if (lower.includes("incident") || lower.includes("mitigation") || lower.includes("impact")) {
      return "Incident Analyst";
    }
    if (lower.includes("route") || lower.includes("transit") || lower.includes("port") || lower.includes("logistics")) {
      return "Routing Advisor";
    }
    if (lower.includes("governance") || lower.includes("checkpoint") || lower.includes("approval") || lower.includes("policy")) {
      return "Governance Assistant";
    }
    if (lower.includes("supplier") || lower.includes("duns") || lower.includes("exposure score") || lower.includes("refinery")) {
      return "Supply Chain Analyst";
    }
    if (lower.includes("risk") || lower.includes("exposure") || lower.includes("geopolitical")) {
      return "Risk Analyst";
    }
    return "Energy Intelligence Analyst";
  };

  const formattedTime = () => {
    if (!timestamp) return "";
    try {
      const d = new Date(timestamp);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return "";
    }
  };

  return (
    <div className={`flex gap-3 max-w-[85%] ${isUser ? "self-end flex-row-reverse" : "self-start"}`}>
      {/* Avatar Icon */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border text-[10px] shadow-sm select-none ${
          isUser
            ? "bg-red-500/10 border-red-500/20 text-red-400"
            : "bg-card border-border text-foreground"
        }`}
      >
        {isUser ? <User size={12} /> : <Bot size={12} className="text-red-500" />}
      </div>

      {/* Bubble Body */}
      <div className="flex flex-col gap-1 min-w-0">
        {/* Expert/Analyst Mode Badge */}
        {!isUser && content && (
          <span className="text-[9px] font-mono uppercase tracking-widest text-red-400/80 font-bold px-0.5">
            {inferAnalystMode(content)}
          </span>
        )}

        <div
          className={`p-3.5 rounded-lg border shadow-sm leading-relaxed relative group ${
            isUser
              ? "bg-red-500/[0.04] border-red-500/20 text-foreground rounded-tr-none"
              : "bg-card/45 border-border rounded-tl-none backdrop-blur-xs"
          }`}
        >
          {isUser ? (
            <p className="text-xs text-foreground/95 break-words whitespace-pre-wrap font-sans">
              {content}
            </p>
          ) : (
            <MarkdownRenderer content={content} />
          )}

          {/* Copy response actions */}
          {!isUser && content && (
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
              title="Copy answer"
            >
              {copied ? <Check size={11} className="text-green-500" /> : <Copy size={11} />}
            </button>
          )}
        </div>

        {/* Timestamp */}
        {timestamp && (
          <span className={`text-[9px] font-mono text-muted-foreground/60 flex items-center gap-1 mt-0.5 ${isUser ? "justify-end" : "justify-start"}`}>
            <Clock size={8} /> {formattedTime()}
          </span>
        )}
      </div>
    </div>
  );
};
