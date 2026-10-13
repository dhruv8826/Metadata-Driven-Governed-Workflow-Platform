import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { Plus, Filter, ArrowUpDown, ChevronRight, FileText } from "lucide-react";

export default function DynamicTable({ objectMeta, onSelectRecord, onCreateRecord }) {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [stateFilter, setStateFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const objectType = objectMeta.object_type;
  const fields = (objectMeta.fields || []).filter((f) => f.can_read !== false);
  const states = objectMeta.lifecycle?.states || [];

  useEffect(() => {
    loadRecords();
  }, [objectType, stateFilter]);

  const loadRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (stateFilter) params.state = stateFilter;
      const res = await api.getRecords(objectType, params);
      setRecords(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err.message || "Failed to load records");
    } finally {
      setLoading(false);
    }
  };

  const getStateColor = (state) => {
    switch (state?.toLowerCase()) {
      case "approved":
      case "done":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "submitted":
      case "scheduled":
      case "in progress":
        return "bg-sky-500/20 text-sky-400 border-sky-500/30";
      case "ordered":
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "rejected":
      case "cancelled":
        return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      default:
        return "bg-slate-700/40 text-slate-300 border-slate-600/30";
    }
  };

  return (
    <div className="space-y-4">
      {/* Table Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            {objectMeta.label}
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-normal">
              {total} {total === 1 ? "record" : "records"}
            </span>
          </h2>
          <p className="text-xs text-slate-400">{objectMeta.description || "Managed entity"}</p>
        </div>

        <div className="flex items-center gap-3">
          {/* State Filter */}
          {states.length > 0 && (
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-xs">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="bg-transparent text-white focus:outline-none cursor-pointer"
              >
                <option value="">All States</option>
                {states.map((st) => (
                  <option key={st} value={st} className="bg-slate-900">
                    {st}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Create Button (Subject to Permissions) */}
          {objectMeta.permissions?.can_create && (
            <button
              onClick={onCreateRecord}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-600/30 transition-all"
            >
              <Plus className="w-4 h-4" />
              New {objectMeta.label}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
          {error}
        </div>
      )}

      {/* Table Container */}
      <div className="glass-card rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium">
              <tr>
                <th className="py-3 px-4">ID</th>
                <th className="py-3 px-4">State</th>
                {fields.map((f) => (
                  <th key={f.name} className="py-3 px-4">
                    {f.label}
                  </th>
                ))}
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={fields.length + 3} className="py-8 text-center text-slate-500">
                    Loading records from server...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={fields.length + 3} className="py-12 text-center">
                    <FileText className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    <p className="text-slate-400 font-medium">No records found</p>
                    <p className="text-slate-500 text-[11px] mt-0.5">
                      No data matches current state filter or permissions.
                    </p>
                  </td>
                </tr>
              ) : (
                records.map((rec) => (
                  <tr
                    key={rec.id}
                    onClick={() => onSelectRecord(rec.id)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                      {rec.id.slice(0, 14)}...
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getStateColor(
                          rec.state
                        )}`}
                      >
                        {rec.state}
                      </span>
                    </td>
                    {fields.map((f) => {
                      const val = rec.data?.[f.name];
                      return (
                        <td key={f.name} className="py-3.5 px-4 text-slate-200">
                          {f.type === "checkbox" ? (
                            val ? (
                              <span className="text-emerald-400 font-semibold text-[11px]">Yes</span>
                            ) : (
                              <span className="text-slate-500 text-[11px]">No</span>
                            )
                          ) : val !== undefined && val !== null ? (
                            String(val)
                          ) : (
                            "—"
                          )}
                        </td>
                      );
                    })}
                    <td className="py-3.5 px-4 text-right">
                      <button className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-0.5 ml-auto text-[11px]">
                        View <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
