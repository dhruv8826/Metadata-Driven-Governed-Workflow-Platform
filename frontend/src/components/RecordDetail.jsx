import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  History,
  ShieldAlert,
  Send,
  Edit2,
  AlertTriangle,
  User,
} from "lucide-react";
import DynamicForm from "./DynamicForm";

export default function RecordDetail({ objectMeta, recordId, onBack }) {
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [approvalReason, setApprovalReason] = useState("");
  const [submittingAction, setSubmittingAction] = useState(false);

  const objectType = objectMeta.object_type;
  const fields = (objectMeta.fields || []).filter((f) => f.can_read !== false);
  const transitions = objectMeta.lifecycle?.transitions || [];

  useEffect(() => {
    loadDetail();
  }, [objectType, recordId]);

  const loadDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRecordDetail(objectType, recordId);
      setRecord(data);
    } catch (err) {
      setError(err.message || "Failed to load record details");
    } finally {
      setLoading(false);
    }
  };

  const handleTransition = async (transitionName) => {
    setActionError(null);
    setActionSuccess(null);
    setSubmittingAction(true);
    try {
      const res = await api.triggerTransition(recordId, transitionName);
      setActionSuccess(
        res.requires_approval
          ? "Transition initiated: Pending approval created for authorized approver."
          : `State transitioned to '${res.current_state}' successfully.`
      );
      await loadDetail();
    } catch (err) {
      setActionError(err.message || "Failed to execute state transition");
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleApproval = async (decision) => {
    if (!record?.pending_approval) return;
    setActionError(null);
    setActionSuccess(null);
    setSubmittingAction(true);
    try {
      const res = await api.submitApprovalDecision(
        record.pending_approval.id,
        decision,
        approvalReason
      );
      setActionSuccess(`Request ${decision.toLowerCase()}ed successfully.`);
      setApprovalReason("");
      await loadDetail();
    } catch (err) {
      setActionError(err.message || "Approval decision failed");
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleSaveUpdate = async (updatedData) => {
    try {
      await api.updateRecord(objectType, recordId, updatedData);
      setIsEditing(false);
      await loadDetail();
    } catch (err) {
      throw err;
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-400">Loading record details...</div>;
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        <p className="font-semibold">Access Error</p>
        <p className="text-xs mt-1">{error}</p>
        <button onClick={onBack} className="mt-4 px-3 py-1.5 rounded bg-slate-800 text-xs text-white">
          Back to List
        </button>
      </div>
    );
  }

  // Active transitions applicable from current state
  const availableTransitions = transitions.filter(
    (t) => t.from_state === record.state
  );

  return (
    <div className="space-y-6">
      {/* Top Bar Navigation & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">
                {objectMeta.label} <span className="font-mono text-slate-400 text-sm">#{record.id.slice(0, 8)}</span>
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                {record.state}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                v{record.version}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Created by <span className="text-slate-300 font-medium">{record.created_by}</span> on{" "}
              {new Date(record.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Lifecycle Action Buttons Bar */}
        <div className="flex items-center gap-2">
          {objectMeta.permissions?.can_update && !isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700 transition-colors"
            >
              <Edit2 className="w-3.5 h-3.5" /> Edit Record
            </button>
          )}

          {availableTransitions.map((t) => (
            <button
              key={t.name}
              disabled={submittingAction}
              onClick={() => handleTransition(t.name)}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-600/30 transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {t.label || t.name}
            </button>
          ))}
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* PENDING APPROVAL GOVERNANCE BOX */}
      {record.pending_approval && (
        <div className="glass-card rounded-xl p-5 border border-amber-500/30 bg-amber-500/5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                <Clock className="w-4 h-4 animate-spin" />
                Pending Governance Approval Required
              </div>
              <p className="text-xs text-slate-300 mt-1">
                Requested transition to <strong className="text-white">'{record.pending_approval.target_state}'</strong> by{" "}
                <span className="font-mono text-amber-300">{record.pending_approval.requester_id}</span>.
                Requires approval from role: <strong className="text-amber-400">{record.pending_approval.required_role}</strong>.
              </p>
            </div>
          </div>

          {/* Self-Approval Block Notification */}
          {!record.pending_approval.can_approve && (
            <div className="mt-3 p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <span>
                {localStorage.getItem("active_persona_id") === record.pending_approval.requester_id
                  ? "Self-approval is strictly prohibited by governance rules. Another authorized persona must approve or reject."
                  : `Approval restricted to role: ${record.pending_approval.required_role}.`}
              </span>
            </div>
          )}

          {/* Approval Decision Controls */}
          {record.pending_approval.can_approve && (
            <div className="mt-4 pt-4 border-t border-amber-500/20 space-y-3">
              <input
                type="text"
                value={approvalReason}
                onChange={(e) => setApprovalReason(e.target.value)}
                placeholder="Optional approval/rejection comment..."
                className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  disabled={submittingAction}
                  onClick={() => handleApproval("REJECT")}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/30 text-xs font-semibold transition-all disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" /> Reject
                </button>
                <button
                  disabled={submittingAction}
                  onClick={() => handleApproval("APPROVE")}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all disabled:opacity-50"
                >
                  <CheckCircle className="w-3.5 h-3.5" /> Approve
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Record Content Grid */}
      {isEditing ? (
        <DynamicForm
          objectMeta={objectMeta}
          initialData={record.data}
          onSubmit={handleSaveUpdate}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Record Fields (2 Columns) */}
          <div className="md:col-span-2 glass-card rounded-xl p-6 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 pb-2 border-b border-slate-800 flex items-center justify-between">
              <span>Entity Attributes</span>
              <span className="text-[11px] text-slate-500 font-normal">
                Field-level projection active
              </span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {fields.map((field) => {
                const val = record.data?.[field.name];
                return (
                  <div
                    key={field.name}
                    className={`p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 ${
                      field.type === "text" && field.name === "justification" ? "sm:col-span-2" : ""
                    }`}
                  >
                    <span className="text-[11px] text-slate-400 font-medium block mb-1">
                      {field.label}
                    </span>
                    <span className="text-sm text-white font-medium">
                      {val !== undefined && val !== null ? String(val) : (
                        <span className="text-slate-500 italic">Not set</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* History Timeline & Versions (1 Column) */}
          <div className="glass-card rounded-xl p-6 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 pb-2 border-b border-slate-800 flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-400" />
              <span>Version History</span>
            </h3>

            <div className="space-y-4">
              {(record.versions || []).map((ver, idx) => (
                <div key={ver.version} className="relative pl-6 pb-2 border-l border-slate-800 last:border-0">
                  <div className="absolute -left-1.5 top-0 w-3 h-3 rounded-full bg-indigo-500 border-2 border-slate-900"></div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-white">Version {ver.version}</span>
                    <span className="text-[10px] text-slate-400">
                      {new Date(ver.changed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    State: <span className="text-indigo-300 font-medium">{ver.state}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 flex items-center gap-1 mt-1">
                    <User className="w-3 h-3" /> By {ver.changed_by}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
