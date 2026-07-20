import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Maximize2, Minimize2, Trash2, Cpu, Activity, Info } from "lucide-react";
import { useChatbot, ActiveContext } from "./hooks/useChatbot";
import { ChatWindow } from "./ChatWindow";
import { ChatInput } from "./ChatInput";
import { SuggestionChips } from "./SuggestionChips";

interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  page: string;
  initialContext?: Partial<ActiveContext>;
}

export const ChatbotDrawer: React.FC<CopilotDrawerProps> = ({
  isOpen,
  onClose,
  page,
  initialContext,
}) => {
  const [width, setWidth] = useState(420); // Normal width preset
  const isResizing = useRef(false);

  // Custom active context parameters
  const [activeContext, setActiveContext] = useState<ActiveContext>({
    page,
  });

  // Load useChatbot hook
  const {
    messages,
    suggestions,
    isGenerating,
    error,
    sendMessage,
    stopGeneration,
    clearHistory,
    retryLastMessage,
  } = useChatbot(page);

  // Sync active parameters
  useEffect(() => {
    setActiveContext((prev) => ({
      ...prev,
      page,
      ...initialContext,
    }));
  }, [page, initialContext]);

  // Handle Dynamic open-copilot Window Events
  useEffect(() => {
    const handleOpenCopilot = (event: Event) => {
      const customEvent = event as CustomEvent<any>;
      if (customEvent.detail) {
        const detail = customEvent.detail;
        
        // Sync context params
        setActiveContext((prev) => ({
          ...prev,
          ...detail,
          page: detail.page || page,
        }));

        // Send message immediately if query is provided
        if (detail.message) {
          sendMessage(detail.message, {
            page: detail.page || page,
            incidentId: detail.incidentId,
            supplierId: detail.supplierId,
            routeId: detail.routeId,
            workflowId: detail.workflowId,
            filters: detail.filters,
            selectedObjects: detail.selectedObjects,
          });
        }
      }
    };

    window.addEventListener("open-copilot", handleOpenCopilot);
    return () => {
      window.removeEventListener("open-copilot", handleOpenCopilot);
    };
  }, [page, sendMessage]);

  // Mouse drag resizing logic (between 350px and 900px)
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.classList.add("select-none");
    document.body.style.cursor = "ew-resize";
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 350 && newWidth <= 900) {
        setWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.classList.remove("select-none");
        document.body.style.cursor = "";
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const toggleExpand = () => {
    setWidth((prev) => (prev > 500 ? 420 : 700));
  };

  const getPageTitle = (p: string) => {
    const mapping: Record<string, string> = {
      dashboard: "Command Center",
      incidents: "Incidents List",
      "incident-simulator": "Incidents Simulator",
      network: "Supplier Network Graph",
      compliance: "Governance & Approvals",
      "route-viewer": "Logistics & Routing",
      intelligence: "Global Market Intelligence",
    };
    return mapping[p] || "Command Center";
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%", opacity: 0.95 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0.95 }}
          transition={{ type: "spring", damping: 25, stiffness: 220 }}
          style={{ width }}
          className="fixed top-0 right-0 h-screen z-40 bg-card/85 backdrop-blur-xl border-l border-border shadow-[0_0_50px_rgba(0,0,0,0.4)] flex flex-row"
        >
          {/* Resize Handle Drag Bar */}
          <div
            onMouseDown={startResize}
            className="w-[3px] hover:w-[6px] h-full cursor-ew-resize bg-border hover:bg-red-500/50 transition-all shrink-0 relative"
          />

          {/* Drawer Inner Panel */}
          <div className="flex-1 flex flex-col min-w-0 h-full">
            {/* Header section */}
            <header className="px-4 py-3.5 border-b border-border flex items-center justify-between bg-card/90 backdrop-blur-md select-none shrink-0">
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-1.5">
                  <Activity size={12} className="text-red-500 animate-pulse" />
                  <h2 className="text-xs font-headline font-bold uppercase tracking-widest text-foreground">
                    Praecantator AI
                  </h2>
                </div>
                <div className="text-[10px] text-muted-foreground/80 font-mono mt-1 flex items-center gap-1">
                  <Info size={9} /> Context: <span className="text-foreground/90 font-sans font-semibold">{getPageTitle(activeContext.page)}</span>
                </div>
              </div>

              {/* Header Buttons */}
              <div className="flex items-center gap-1">
                {/* Clear Conversation */}
                <button
                  onClick={clearHistory}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-red-400 transition-colors cursor-pointer"
                  title="Clear conversation"
                >
                  <Trash2 size={13} />
                </button>

                {/* Expand / Collapse Toggle */}
                <button
                  onClick={toggleExpand}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  title={width > 500 ? "Collapse to 420px" : "Expand to 700px"}
                >
                  {width > 500 ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
                </button>

                {/* Close Drawer */}
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  title="Close panel"
                >
                  <X size={13} />
                </button>
              </div>
            </header>

            {/* Conversation Window */}
            <ChatWindow
              messages={messages}
              isGenerating={isGenerating}
              error={error}
              onRetry={retryLastMessage}
            />

            {/* Suggestion action chips */}
            <SuggestionChips
              suggestions={suggestions}
              onSelectSuggestion={(text) => sendMessage(text, activeContext)}
            />

            {/* Chat Input */}
            <ChatInput
              onSend={(text) => sendMessage(text, activeContext)}
              onStop={stopGeneration}
              isGenerating={isGenerating}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
export default ChatbotDrawer;
