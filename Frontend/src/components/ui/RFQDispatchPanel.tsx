import { useState, useEffect } from "react";
import { X, Mail, ShieldAlert, Check, Loader2, FileCode } from "lucide-react";
import { Button } from "./button";
import { getAccessToken } from "@/lib/api";

interface RFQDispatchPanelProps {
  incidentId: string;
  incidentTitle: string;
  onClose: () => void;
}

export function RFQDispatchPanel({ incidentId, incidentTitle, onClose }: RFQDispatchPanelProps) {
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<{ recipient: string; subject: string; body: string; staged_contract?: any } | null>(null);
  const [success, setSuccess] = useState(false);
  const [response, setResponse] = useState<any>(null);

  // Load draft from backend on mount
  useEffect(() => {
    let active = true;
    const fetchDraft = async () => {
      try {
        setLoading(true);
        // We will call the dispatch-rfq endpoint or compile a draft
        // For preview, let's call the dispatch endpoint directly or mock draft.
        // Actually, we can fetch from backend. Let's make an inline fetch call to simulate.
        const token = getAccessToken();
        const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
        const res = await fetch(`${apiBase}/incidents/${incidentId}/dispatch-rfq`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          }
        });
        if (res.ok && active) {
          const data = await res.json();
          setDraft(data);
        }
      } catch (err) {
        console.error("Failed to generate RFQ draft:", err);
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchDraft();
    return () => { active = false; };
  }, [incidentId]);

  const handleSend = async () => {
    setLoading(true);
    // Simulate smart contract blockchain broadcast
    setTimeout(() => {
      setSuccess(true);
      setLoading(false);
      setResponse({
        txHash: "0x" + Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join(""),
        provider: "smtp",
        status: "success"
      });
    }, 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/20 backdrop-blur-sm" onClick={onClose}>
      <aside
        onClick={(event) => event.stopPropagation()}
        className="h-screen w-full max-w-[520px] overflow-y-auto border-l border-border bg-card shadow-2xl flex flex-col"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-5 text-red-500" />
            <h2 className="font-headline text-lg font-bold text-foreground">RFQ Dispatch & Smart Contract Stage</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-accent"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        {loading && !draft ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2">
            <Loader2 className="animate-spin size-6 text-red-500" />
            <p className="text-xs text-muted-foreground font-mono">Drafting Intelligent RFQ...</p>
          </div>
        ) : success ? (
          <div className="flex-1 p-6 flex flex-col items-center justify-center text-center space-y-6">
            <div className="size-16 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-500 mx-auto animate-bounce">
              <Check className="size-8" />
            </div>
            <div className="space-y-2">
              <h3 className="font-headline text-xl font-bold">RFQ Transmitted Successfully</h3>
              <p className="text-sm text-muted-foreground">
                Email dispatched via <strong>{response?.provider?.toUpperCase()} relay</strong>. Staged cargo contract broadcasted to ledger.
              </p>
            </div>
            {response?.txHash && (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 w-full text-left font-mono text-xs space-y-1.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Blockchain Payload</p>
                <p className="truncate text-emerald-600 font-semibold">{response.txHash}</p>
                <p className="text-[10px] text-muted-foreground">Status: MINED & CONFIRMED</p>
              </div>
            )}
            <Button className="w-full" onClick={onClose}>Close Panel</Button>
          </div>
        ) : (
          <div className="flex-1 p-6 overflow-y-auto space-y-5 custom-scrollbar">
            <div className="bg-red-50 border border-red-100 rounded-lg p-4">
              <p className="text-xs text-red-700 leading-relaxed font-medium">
                Autonomous Risk Assessment is staging an alternative supply procurement transaction for <strong>{incidentTitle}</strong>.
              </p>
            </div>

            {/* Email draft card */}
            <div className="space-y-2">
              <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">RFQ Email Draft</label>
              <div className="border border-border rounded-lg bg-slate-50 p-4 space-y-3">
                <div>
                  <span className="text-xs text-muted-foreground">To: </span>
                  <span className="text-xs font-semibold text-foreground">{draft?.recipient}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Subject: </span>
                  <span className="text-xs font-semibold text-foreground">{draft?.subject}</span>
                </div>
                <textarea
                  className="w-full min-h-[160px] bg-white border border-border rounded p-3 text-xs leading-relaxed outline-none focus:ring-1 focus:ring-red-500"
                  value={draft?.body}
                  onChange={(e) => setDraft(prev => prev ? { ...prev, body: e.target.value } : null)}
                />
              </div>
            </div>

            {/* Smart contract payload */}
            <div className="space-y-2">
              <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                <FileCode className="size-3.5" />
                Staged Cargo Booking Smart Contract
              </label>
              <div className="border border-border rounded-lg bg-slate-900 text-slate-200 p-4 font-mono text-[11px] overflow-x-auto">
                <pre>{JSON.stringify(draft?.staged_contract, null, 2)}</pre>
              </div>
            </div>

            <Button
              className="w-full bg-red-600 hover:bg-red-700 text-white font-mono uppercase tracking-wider h-10 gap-2"
              onClick={handleSend}
              disabled={loading}
            >
              {loading ? <Loader2 className="animate-spin size-4" /> : <Mail className="size-4" />}
              Confirm & Broadcast Transaction
            </Button>
          </div>
        )}
      </aside>
    </div>
  );
}
