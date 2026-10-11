import React, { useState, useEffect } from "react";
import { api } from "./services/api";
import ContextSwitcher from "./components/ContextSwitcher";
import DynamicTable from "./components/DynamicTable";
import DynamicForm from "./components/DynamicForm";
import RecordDetail from "./components/RecordDetail";
import DashboardView from "./components/DashboardView";
import AuditView from "./components/AuditView";
import ApprovalsView from "./components/ApprovalsView";
import AdminStudio from "./components/AdminStudio";
import {
  Layers,
  BarChart3,
  Clock,
  Shield,
  Settings,
  FolderKanban,
  FileText,
} from "lucide-react";

export default function App() {
  const [objects, setObjects] = useState([]);
  const [selectedObjectType, setSelectedObjectType] = useState(null);
  const [selectedObjectMeta, setSelectedObjectMeta] = useState(null);
  const [activeTab, setActiveTab] = useState("records"); // "records", "dashboard", "approvals", "audit", "admin"
  const [viewMode, setViewMode] = useState("list"); // "list", "detail", "create"
  const [selectedRecordId, setSelectedRecordId] = useState(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Reload metadata whenever tenant or persona changes
  const handleContextChange = () => {
    setViewMode("list");
    setSelectedRecordId(null);
    loadMetadata();
  };

  useEffect(() => {
    loadMetadata();
  }, []);

  const loadMetadata = async () => {
    setLoading(true);
    try {
      const objList = await api.getMetadataObjects();
      setObjects(objList || []);

      if (objList && objList.length > 0) {
        // Keep current object if still available, or pick first
        const exists = objList.find((o) => o.object_type === selectedObjectType);
        const targetType = exists ? selectedObjectType : objList[0].object_type;
        setSelectedObjectType(targetType);

        const meta = await api.getMetadataObject(targetType);
        setSelectedObjectMeta(meta);
      } else {
        setSelectedObjectType(null);
        setSelectedObjectMeta(null);
      }

      // Check pending approvals count
      const pending = await api.getPendingApprovals();
      setPendingApprovalsCount(pending?.length || 0);
    } catch (err) {
      console.error("Failed to load metadata:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectObject = async (objType) => {
    setSelectedObjectType(objType);
    setActiveTab("records");
    setViewMode("list");
    setSelectedRecordId(null);
    try {
      const meta = await api.getMetadataObject(objType);
      setSelectedObjectMeta(meta);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSelectRecord = (id) => {
    setSelectedRecordId(id);
    setViewMode("detail");
  };

  const handleCreateRecord = () => {
    setViewMode("create");
  };

  const handleCreateSubmit = async (formData) => {
    await api.createRecord(selectedObjectType, formData);
    setViewMode("list");
    // Reload pending count and metadata
    const pending = await api.getPendingApprovals();
    setPendingApprovalsCount(pending?.length || 0);
  };

  const currentRole = localStorage.getItem("active_persona_role") || "Requester";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* 1. Context Switcher Header */}
      <ContextSwitcher onContextChange={handleContextChange} />

      {/* 2. Main Navigation Bar (Domain Agnostic) */}
      <nav className="glass-panel border-b border-slate-800 px-6 py-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Dynamic Entity Links derived completely from metadata */}
          <div className="flex items-center gap-1 overflow-x-auto">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mr-2 flex items-center gap-1">
              <Layers className="w-3.5 h-3.5" /> Entities:
            </span>
            {objects.map((obj) => (
              <button
                key={obj.object_type}
                onClick={() => handleSelectObject(obj.object_type)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  activeTab === "records" && selectedObjectType === obj.object_type
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-300 hover:bg-slate-800/80 hover:text-white"
                }`}
              >
                <FolderKanban className="w-3.5 h-3.5" />
                {obj.label}
              </button>
            ))}
          </div>

          {/* System Workspace Tabs */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                activeTab === "dashboard"
                  ? "bg-slate-800 text-indigo-400 border border-slate-700"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Dashboard
            </button>

            <button
              onClick={() => setActiveTab("approvals")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 relative ${
                activeTab === "approvals"
                  ? "bg-slate-800 text-amber-400 border border-slate-700"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              Approvals
              {pendingApprovalsCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-amber-500 text-slate-950 font-bold text-[10px] flex items-center justify-center">
                  {pendingApprovalsCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("audit")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                activeTab === "audit"
                  ? "bg-slate-800 text-emerald-400 border border-slate-700"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              Audit Log
            </button>

            {currentRole === "Admin" && (
              <button
                onClick={() => setActiveTab("admin")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  activeTab === "admin"
                    ? "bg-slate-800 text-violet-400 border border-slate-700"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                }`}
              >
                <Settings className="w-3.5 h-3.5" />
                Admin Studio
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* 3. Main Workspace Container */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {loading ? (
          <div className="py-20 text-center text-slate-500">Loading metadata platform...</div>
        ) : activeTab === "dashboard" ? (
          <DashboardView />
        ) : activeTab === "approvals" ? (
          <ApprovalsView
            onSelectRecord={(objType, recId) => {
              handleSelectObject(objType);
              handleSelectRecord(recId);
            }}
          />
        ) : activeTab === "audit" ? (
          <AuditView />
        ) : activeTab === "admin" ? (
          <AdminStudio />
        ) : (
          /* Active Entity Workspace */
          selectedObjectMeta && (
            <div>
              {viewMode === "list" && (
                <DynamicTable
                  objectMeta={selectedObjectMeta}
                  onSelectRecord={handleSelectRecord}
                  onCreateRecord={handleCreateRecord}
                />
              )}

              {viewMode === "create" && (
                <DynamicForm
                  objectMeta={selectedObjectMeta}
                  onSubmit={handleCreateSubmit}
                  onCancel={() => setViewMode("list")}
                />
              )}

              {viewMode === "detail" && selectedRecordId && (
                <RecordDetail
                  objectMeta={selectedObjectMeta}
                  recordId={selectedRecordId}
                  onBack={() => {
                    setViewMode("list");
                    setSelectedRecordId(null);
                  }}
                />
              )}
            </div>
          )
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 px-6 py-4 text-center text-xs text-slate-500">
        GovFlow &bull; Domain-Agnostic Governed Workflow Platform &bull; Zero Domain Code Guarantee
      </footer>
    </div>
  );
}
