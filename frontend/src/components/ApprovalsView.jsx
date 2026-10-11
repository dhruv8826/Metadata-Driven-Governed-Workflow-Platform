import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { CheckCircle2, XCircle, Clock, AlertTriangle, RefreshCw, Check } from "lucide-react";

export default function ApprovalsView({ onSelectRecord }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [decisionNotes, setDecisionNotes] = useState({});
  const [submittingId, setSubmittingId] = useState(null);

  useEffect(() => {
    loadApprovals();
  }, [localStorage.getItem("active_tenant_id"), localStorage.getItem("active_persona_role")]);

  const loadApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPendingApprovals();
      setApprovals(data || []);
    } catch (err) {
      setError(err.message || "Failed to load pending approvals");
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (approvalId, decision) => {
    setSubmittingId(approvalId);
    setError(null);
    setSuccess(null);
    try {
      const note = decisionNotes[approvalId] || "";
      await api.submitApprovalDecision(approvalId, decision, note);
      setSuccess(`Approval request successfully ${decision.toLowerCase()}ed.`);
      await loadApprovals();
    } catch (err) {
      setError(err.message || "Approval decision failed");
    } finally {
      setSubmittingId(null);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-400">Loading pending approvals...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            Pending Governance Approvals ({approvals.length})
          </h2>
          <p className="text-xs text-slate-400">
            Reviews required by governance policies. Self-approvals are strictly barred.
          </p>
        </div>

        <button
          onClick={loadApprovals}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {success && (
        <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
          <Check className="w-4 h-4 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {approvals.length === 0 ? (
        <div className="glass-card rounded-xl p-12 text-center border border-slate-800">
          <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3 opacity-80" />
          <h3 className="text-base font-semibold text-white">All Caught Up!</h3>
          <p className="text-xs text-slate-400 mt-1">
            There are currently zero pending approvals awaiting your role.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {approvals.map((appr) => {
            const isSubmitting = submittingId === appr.id;

            return (
              <div
                key={appr.id}
                className="glass-card rounded-xl p-5 border border-slate-800 space-y-4 hover:border-slate-700 transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      Requires {appr.required_role}
                    </span>
                    <h4 className="text-sm font-bold text-white mt-2">
                      Transition to '{appr.target_state}'
                    </h4>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      Entity: {appr.object_type} (#{appr.record_id.slice(0, 8)})
                    </p>
                  </div>
                  <button
                    onClick={() => onSelectRecord(appr.object_type, appr.record_id)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    View Details
                  </button>
                </div>

                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300 space-y-1">
                  <div>
                    <span className="text-slate-500">Requester:</span>{" "}
                    <span className="font-mono text-slate-200">{appr.requester_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Current State:</span>{" "}
                    <span className="font-semibold text-indigo-300">{appr.current_record_state}</span>
                  </div>
                </div>

                {!appr.can_approve ? (
                  <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>
                      {localStorage.getItem("active_persona_id") === appr.requester_id
                        ? "Self-approval blocked: You cannot approve your own submission."
                        : `Only ${appr.required_role} may approve.`}
                    </span>
                  </div>
                ) : (
                  <div className="space-y-3 pt-2 border-t border-slate-800">
                    <input
                      type="text"
                      placeholder="Approval / Rejection justification..."
                      value={decisionNotes[appr.id] || ""}
                      onChange={(e) =>
                        setDecisionNotes({ ...decisionNotes, [appr.id]: e.target.value })
                      }
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />

                    <div className="flex items-center justify-end gap-2">
                      <button
                        disabled={isSubmitting}
                        onClick={() => handleDecision(appr.id, "REJECT")}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 border border-rose-500/30 text-xs font-semibold transition-all disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Reject
                      </button>
                      <button
                        disabled={isSubmitting}
                        onClick={() => handleDecision(appr.id, "APPROVE")}
                        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/30 transition-all disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
