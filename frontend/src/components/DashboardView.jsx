import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { BarChart3, TrendingUp, Lock, RefreshCw, Layers } from "lucide-react";

export default function DashboardView() {
  const [dashboards, setDashboards] = useState([]);
  const [activeDashId, setActiveDashId] = useState(null);
  const [metricsData, setMetricsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDashboards();
  }, [localStorage.getItem("active_tenant_id"), localStorage.getItem("active_persona_role")]);

  const loadDashboards = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.getDashboards();
      setDashboards(list);
      if (list.length > 0) {
        const targetId = list[0].id;
        setActiveDashId(targetId);
        const data = await api.getDashboardMetrics(targetId);
        setMetricsData(data);
      }
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDashboard = async (id) => {
    setActiveDashId(id);
    setLoading(true);
    try {
      const data = await api.getDashboardMetrics(id);
      setMetricsData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-400">Loading analytics & widgets...</div>;
  }

  if (error) {
    return <div className="p-6 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">{error}</div>;
  }

  const widgets = metricsData?.widgets || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-400" />
            {metricsData?.title || "Analytics Dashboard"}
          </h2>
          <p className="text-xs text-slate-400">
            Driven by declarative widget metadata and evaluated against viewer permissions.
          </p>
        </div>

        <button
          onClick={loadDashboards}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Widgets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {widgets.map((w) => {
          if (w.status === "RESTRICTED") {
            return (
              <div
                key={w.widget_id}
                className="glass-card rounded-xl p-6 border border-amber-500/30 bg-amber-500/5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-amber-400 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider">Restricted Widget</span>
                    <Lock className="w-4 h-4" />
                  </div>
                  <h4 className="text-sm font-semibold text-white">{w.title}</h4>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    {w.error || "This metric is concealed because your role does not have read permissions for the required fields."}
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-amber-500/20 text-[11px] text-amber-400/80 font-mono">
                  Zero Data Leakage Enforced
                </div>
              </div>
            );
          }

          if (w.type === "kpi") {
            return (
              <div
                key={w.widget_id}
                className="glass-card rounded-xl p-6 border border-slate-800 hover:border-slate-700 transition-all"
              >
                <div className="flex items-center justify-between text-slate-400 mb-2">
                  <span className="text-xs font-medium uppercase tracking-wider">{w.title}</span>
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-3xl font-extrabold text-white mt-2">
                  {typeof w.value === "number" ? w.value.toLocaleString() : w.value}
                </div>
                <p className="text-[11px] text-slate-400 mt-2">
                  Aggregation: <span className="font-semibold text-slate-300 uppercase">{w.aggregation}</span>
                </p>
              </div>
            );
          }

          if (w.type === "chart") {
            const chartData = w.data || [];
            const maxValue = Math.max(...chartData.map((d) => d.value), 1);

            return (
              <div
                key={w.widget_id}
                className="md:col-span-2 glass-card rounded-xl p-6 border border-slate-800"
              >
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h4 className="text-sm font-semibold text-white">{w.title}</h4>
                    <p className="text-xs text-slate-400">Grouped by {w.group_by}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {chartData.map((item) => {
                    const pct = Math.round((item.value / maxValue) * 100);
                    return (
                      <div key={item.label} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-300 font-medium">{item.label}</span>
                          <span className="text-white font-mono font-semibold">
                            {typeof item.value === "number" ? item.value.toLocaleString() : item.value}
                          </span>
                        </div>
                        <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }

          if (w.type === "table") {
            return (
              <div
                key={w.widget_id}
                className="md:col-span-3 glass-card rounded-xl p-6 border border-slate-800"
              >
                <h4 className="text-sm font-semibold text-white mb-4">{w.title}</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/60 text-slate-400">
                      <tr>
                        <th className="py-2.5 px-3">ID</th>
                        <th className="py-2.5 px-3">State</th>
                        <th className="py-2.5 px-3">Data</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {(w.items || []).map((it) => (
                        <tr key={it.id}>
                          <td className="py-2.5 px-3 font-mono text-slate-400">{it.id.slice(0, 10)}...</td>
                          <td className="py-2.5 px-3 text-slate-200">{it.state}</td>
                          <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">
                            {JSON.stringify(it.data)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }

          return null;
        })}
      </div>
    </div>
  );
}
