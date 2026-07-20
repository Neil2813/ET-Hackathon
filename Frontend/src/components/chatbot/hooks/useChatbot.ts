import { useState, useEffect, useRef, useCallback } from "react";
import { copilotApi as chatbotApi, CopilotMessage } from "../services/chatbotApi";

export interface ActiveContext {
  page: string;
  incidentId?: string;
  supplierId?: string;
  routeId?: string;
  workflowId?: string;
  filters?: Record<string, any>;
  selectedObjects?: any[];
}

/** Tokens that indicate a backend-level error surfaced inside the SSE stream */
const BACKEND_ERROR_PREFIXES = [
  "Error: GROQ_API_KEY",
  "Error calling Groq API",
  "Internal Server Error",
  "Error: ",
];

function isBackendErrorToken(token: string): boolean {
  return BACKEND_ERROR_PREFIXES.some((prefix) => token.startsWith(prefix));
}

export function useChatbot(page: string) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  // Track the last user message + context to support retry
  const lastRequestRef = useRef<{ text: string; context: ActiveContext } | null>(null);
  // Flag: did we encounter a backend error token during the current stream?
  const streamErrorRef = useRef<string | null>(null);

  // Load history from DB — always syncs with server ground truth
  const loadHistory = useCallback(async () => {
    try {
      setError(null);
      const res = await chatbotApi.getHistory();
      setMessages(res.messages || []);
    } catch (err: any) {
      console.error("Failed to load chat history:", err);
      setError("Failed to load conversation history.");
    }
  }, []);

  // Load suggestion chips dynamically
  const loadSuggestions = useCallback(async (activePage: string) => {
    try {
      const res = await chatbotApi.getSuggestions(activePage);
      setSuggestions(res.suggestions || []);
    } catch (err) {
      console.error("Failed to load suggestions:", err);
    }
  }, []);

  // Clear current conversation
  const clearHistory = useCallback(async () => {
    try {
      setError(null);
      await chatbotApi.clearHistory();
      setMessages([]);
      lastRequestRef.current = null;
      loadSuggestions(page);
    } catch (err) {
      setError("Failed to clear chat history.");
    }
  }, [page, loadSuggestions]);

  // Stop current streaming generation
  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      // isGenerating is cleared by the onDone callback triggered by AbortError in chatbotApi
    }
  }, []);

  // Core send logic — used by both sendMessage and retryLastMessage
  const _executeStream = useCallback(
    async (text: string, context: ActiveContext) => {
      // Abort any ongoing stream first
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      setError(null);
      streamErrorRef.current = null;
      setIsGenerating(true);

      // Append optimistic user bubble + empty assistant placeholder
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      let accumulatedText = "";

      await chatbotApi.streamChat(
        {
          message: text,
          page: context.page,
          incidentId: context.incidentId,
          supplierId: context.supplierId,
          routeId: context.routeId,
          workflowId: context.workflowId,
          filters: context.filters,
          selectedObjects: context.selectedObjects,
        },

        // onChunk — detect backend error tokens inline; otherwise update bubble
        (token) => {
          if (isBackendErrorToken(token) || streamErrorRef.current) {
            // Accumulate error text (may arrive in multiple tokens)
            streamErrorRef.current = (streamErrorRef.current ?? "") + token;
            return;
          }
          accumulatedText += token;
          setMessages((prev) => {
            const next = [...prev];
            if (next.length > 0) {
              next[next.length - 1] = { role: "assistant", content: accumulatedText };
            }
            return next;
          });
        },

        // onDone — check if we had a backend error token; if so, surface it as UI error
        () => {
          setIsGenerating(false);
          abortControllerRef.current = null;

          if (streamErrorRef.current) {
            const errMsg = streamErrorRef.current;
            streamErrorRef.current = null;
            // Remove the blank assistant placeholder since nothing was rendered
            setMessages((prev) => {
              const next = [...prev];
              if (
                next.length > 0 &&
                next[next.length - 1].role === "assistant" &&
                next[next.length - 1].content === ""
              ) {
                next.pop();
              }
              return next;
            });
            setError(errMsg + " — Check your backend configuration, then click Retry.");
          }
        },

        // onError — network / HTTP failure
        (err) => {
          console.error("Copilot stream error:", err);
          setError("Connection failed. Check your backend is running, then click Retry.");
          setIsGenerating(false);
          abortControllerRef.current = null;
          streamErrorRef.current = null;
          // Remove empty assistant placeholder
          setMessages((prev) => {
            const next = [...prev];
            if (
              next.length > 0 &&
              next[next.length - 1].role === "assistant" &&
              next[next.length - 1].content === ""
            ) {
              next.pop();
            }
            return next;
          });
        },

        controller.signal
      );
    },
    []
  );

  // Send a new message
  const sendMessage = useCallback(
    async (text: string, context: ActiveContext) => {
      if (!text.trim()) return;
      lastRequestRef.current = { text, context };
      await _executeStream(text, context);
    },
    [_executeStream]
  );

  // Retry the last failed message.
  // Reloads history from the server first to get the true ground truth
  // (avoids duplicate bubbles from local state guessing).
  const retryLastMessage = useCallback(async () => {
    if (!lastRequestRef.current) return;
    const { text, context } = lastRequestRef.current;
    setError(null);

    // Re-sync with server so we don't double-count locally-added bubbles
    try {
      const res = await chatbotApi.getHistory();
      setMessages(res.messages || []);
    } catch {
      // If history load fails just strip trailing failed bubbles locally
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant" && next[next.length - 1].content === "") {
          next.pop();
        }
        if (next.length > 0 && next[next.length - 1].role === "user") {
          next.pop();
        }
        return next;
      });
    }

    await _executeStream(text, context);
  }, [_executeStream]);

  // Initial load
  useEffect(() => {
    loadHistory();
    loadSuggestions(page);
  }, [page, loadHistory, loadSuggestions]);

  return {
    messages,
    suggestions,
    isGenerating,
    error,
    sendMessage,
    stopGeneration,
    clearHistory,
    retryLastMessage,
    refreshSuggestions: loadSuggestions,
  };
}
