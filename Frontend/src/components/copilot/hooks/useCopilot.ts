import { useState, useEffect, useRef, useCallback } from "react";
import { copilotApi, CopilotMessage } from "../services/copilotApi";

export interface ActiveContext {
  page: string;
  incidentId?: string;
  supplierId?: string;
  routeId?: string;
  workflowId?: string;
  filters?: Record<string, any>;
  selectedObjects?: any[];
}

export function useCopilot(page: string) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load history from DB
  const loadHistory = useCallback(async () => {
    try {
      setError(null);
      const res = await copilotApi.getHistory();
      setMessages(res.messages || []);
    } catch (err: any) {
      console.error("Failed to load chat history:", err);
      setError("Failed to load conversation history.");
    }
  }, []);

  // Load suggestion chips dynamically
  const loadSuggestions = useCallback(async (activePage: string) => {
    try {
      const res = await copilotApi.getSuggestions(activePage);
      setSuggestions(res.suggestions || []);
    } catch (err) {
      console.error("Failed to load suggestions:", err);
    }
  }, []);

  // Clear current conversation
  const clearHistory = useCallback(async () => {
    try {
      setError(null);
      await copilotApi.clearHistory();
      setMessages([]);
      // Reload page-based suggestions
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
      setIsGenerating(false);
    }
  }, []);

  // Send message
  const sendMessage = useCallback(
    async (text: string, context: ActiveContext) => {
      if (!text.trim()) return;

      // Abort any ongoing stream first
      stopGeneration();

      setError(null);
      setIsGenerating(true);

      const userMessage: CopilotMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMessage]);

      const assistantMessageIndex = messages.length + 1; // Anticipated index
      
      // Add empty assistant response to update in real time
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      let accumulatedText = "";

      await copilotApi.streamChat(
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
        // onChunk
        (token) => {
          accumulatedText += token;
          setMessages((prev) => {
            const next = [...prev];
            if (next.length > 0) {
              next[next.length - 1] = {
                role: "assistant",
                content: accumulatedText,
              };
            }
            return next;
          });
        },
        // onDone
        () => {
          setIsGenerating(false);
          abortControllerRef.current = null;
        },
        // onError
        (err) => {
          console.error("Copilot stream error:", err);
          setError("An error occurred during generation. Please try again.");
          setIsGenerating(false);
          abortControllerRef.current = null;
        },
        controller.signal
      );
    },
    [messages.length, stopGeneration]
  );

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
    refreshSuggestions: loadSuggestions,
  };
}
