import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { Shield, ChevronDown, ChevronRight, RefreshCw, AlertCircle, CheckCircle, Ban, Clock } from "lucide-react";

export default function AuditView() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    loadLogs();
  }, [outcomeFilter]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const params = { limit: 50 };
      if (outcomeFilter) params.outcome = outcomeFilter;
      const data = await api.getAuditTrail(params);
      setLogs(data || []);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  const getOutcomeBadge = (outcome) => {
    switch (outcome) {
      case "SUCCESS":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle className="w-3 h-3" /> SUCCESS
          </span>
        );
      case "DENIED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <Ban className="w-3 h-3" /> DENIED
          </span>
        );
      case "GUARD_FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <AlertCircle className="w-3 h-3" /> GUARD FAILED
          </span>
        );
      case "PENDING_APPROVAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <Clock className="w-3 h-3" /> PENDING
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            {outcome}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400" />
            Append-Only Audit Log & Governance Evidence
          </h2>
          <p className="text-xs text-slate-400">
            Immutable log recording every mutation, transition, approval, and denied access attempt.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-xs text-white px-3 py-1.5 rounded-lg focus:outline-none cursor-pointer"
          >
            <option value="">All Outcomes</option>
            <option value="SUCCESS">Success Only</option>
            <option value="DENIED">Denied / Violations Only</option>
            <option value="GUARD_FAILED">Guard Failures Only</option>
            <option value="PENDING_APPROVAL">Pending Approval</option>
          </select>

          <button
            onClick={loadLogs}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      <div className="glass-card rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium">
              <tr>
                <th className="py-3 px-4 w-10"></th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Target Entity</th>
                <th className="py-3 px-4">Outcome</th>
                <th className="py-3 px-4">Reason / Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500">
                    No audit records found.
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  const hasDiffs = log.field_diffs && Object.keys(log.field_diffs).length > 0;

                  return (
                    <React.Fragment key={log.id}>
                      <tr
                        onClick={() => hasDiffs && setExpandedId(isExpanded ? null : log.id)}
                        className={`hover:bg-slate-800/30 transition-colors ${
                          hasDiffs ? "cursor-pointer" : ""
                        }`}
                      >
                        <td className="py-3 px-4 text-slate-500">
                          {hasDiffs && (
                            <span>{isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="py-3 px-4 font-medium text-slate-200">{log.actor_id}</td>
                        <td className="py-3 px-4 text-slate-400">{log.actor_role}</td>
                        <td className="py-3 px-4 font-semibold text-white">{log.action}</td>
                        <td className="py-3 px-4 text-slate-400">
                          {log.object_type} {log.record_id ? `(#${log.record_id.slice(0, 6)})` : ""}
                        </td>
                        <td className="py-3 px-4">{getOutcomeBadge(log.outcome)}</td>
                        <td className="py-3 px-4 text-slate-300 max-w-xs truncate">{log.reason || "—"}</td>
                      </tr>

                      {/* Expandable Field Diffs */}
                      {isExpanded && hasDiffs && (
                        <tr className="bg-slate-950/60">
                          <td colSpan={8} className="py-3 px-8">
                            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                                Granular Field Deltas
                              </p>
                              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                                {Object.entries(log.field_diffs).map(([field, delta]) => (
                                  <div key={field} className="p-2 rounded bg-slate-950 border border-slate-800 text-[11px]">
                                    <span className="font-semibold text-slate-300">{field}:</span>
                                    <div className="flex items-center gap-2 mt-1">
                                      <span className="text-rose-400 line-through">
                                        {delta.old !== null && delta.old !== undefined ? String(delta.old) : "null"}
                                      </span>
                                      <span className="text-slate-500">→</span>
                                      <span className="text-emerald-400 font-medium">
                                        {delta.new !== null && delta.new !== undefined ? String(delta.new) : "null"}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
