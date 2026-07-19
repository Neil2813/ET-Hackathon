import { request, getAccessToken, getUserId } from "@/lib/api";

const API_BASE = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "");

export interface CopilotChatRequest {
  message: string;
  page: string;
  incidentId?: string;
  supplierId?: string;
  routeId?: string;
  workflowId?: string;
  tenantId?: string;
  filters?: Record<string, any>;
  selectedObjects?: any[];
}

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export interface CopilotHistoryResponse {
  conversation_id: string;
  messages: CopilotMessage[];
}

export interface CopilotSuggestionsResponse {
  suggestions: string[];
}

export const copilotApi = {
  getHistory: async (): Promise<CopilotHistoryResponse> => {
    return request<CopilotHistoryResponse>("/copilot/history");
  },

  clearHistory: async (): Promise<{ status: string; message: string }> => {
    return request<{ status: string; message: string }>("/copilot/clear", {
      method: "POST",
    });
  },

  getSuggestions: async (page: string): Promise<CopilotSuggestionsResponse> => {
    return request<CopilotSuggestionsResponse>(`/copilot/suggestions?page=${encodeURIComponent(page)}`);
  },

  streamChat: async (
    payload: CopilotChatRequest,
    onChunk: (token: string) => void,
    onDone: () => void,
    onError: (err: any) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const token = getAccessToken();
    const userId = getUserId();
    
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    if (userId) {
      headers["X-User-Id"] = userId;
    }

    try {
      const response = await fetch(`${API_BASE}/copilot/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `HTTP error ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Response body is not readable.");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last partial line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed === "data: [DONE]") {
            onDone();
            return;
          }
          if (trimmed.startsWith("data: ")) {
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data && typeof data.token === "string") {
                onChunk(data.token);
              }
            } catch (e) {
              // Ignore parse errors on partial streams
            }
          }
        }
      }

      // Check remaining buffer
      if (buffer.startsWith("data: ")) {
        try {
          const data = JSON.parse(buffer.slice(6));
          if (data && typeof data.token === "string") {
            onChunk(data.token);
          }
        } catch (e) {}
      }

      onDone();
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Copilot stream aborted by user.");
      } else {
        onError(err);
      }
    }
  },
};
