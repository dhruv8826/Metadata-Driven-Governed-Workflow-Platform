import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { Settings, Shield, Plus, Save, AlertCircle, CheckCircle, Database } from "lucide-react";

export default function AdminStudio() {
  const [objects, setObjects] = useState([]);
  const [selectedObjType, setSelectedObjType] = useState(null);
  const [objectDetail, setObjectDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldLabel, setNewFieldLabel] = useState("");
  const [newFieldType, setNewFieldType] = useState("text");
  const [newFieldRequired, setNewFieldRequired] = useState(false);
  const [changeReason, setChangeReason] = useState("");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadObjects();
  }, [localStorage.getItem("active_tenant_id")]);

  const loadObjects = async () => {
    setLoading(true);
    try {
      const list = await api.getMetadataObjects();
      setObjects(list);
      if (list.length > 0) {
        selectObject(list[0].object_type);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectObject = async (objType) => {
    setSelectedObjType(objType);
    setMessage(null);
    setError(null);
    try {
      const detail = await api.getMetadataObject(objType);
      setObjectDetail(detail);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleAddField = () => {
    if (!newFieldName.trim() || !newFieldLabel.trim()) {
      setError("Please provide both field identifier and label");
      return;
    }
    const updatedFields = [
      ...(objectDetail.fields || []),
      {
        name: newFieldName.trim().toLowerCase().replace(/\s+/g, "_"),
        label: newFieldLabel.trim(),
        type: newFieldType,
        required: newFieldRequired,
        display_order: (objectDetail.fields || []).length + 1,
      },
    ];
    setObjectDetail({ ...objectDetail, fields: updatedFields });
    setNewFieldName("");
    setNewFieldLabel("");
    setNewFieldRequired(false);
  };

  const handleRemoveField = (fieldName) => {
    if (objectDetail.fields.length <= 1) {
      setError("Destructive Wipeout Prevented: An object schema must have at least one field!");
      return;
    }
    const updatedFields = objectDetail.fields.filter((f) => f.name !== fieldName);
    setObjectDetail({ ...objectDetail, fields: updatedFields });
  };

  const handleSaveSchema = async () => {
    if (!changeReason || changeReason.length < 10) {
      setError("Governance Requirement: A change justification of at least 10 characters is required.");
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        object_type: objectDetail.object_type,
        label: objectDetail.label,
        description: objectDetail.description || "",
        schema_definition: objectDetail.fields.map((f) => ({
          name: f.name,
          label: f.label,
          type: f.type,
          required: f.required,
          options: f.options,
          reference_target: f.reference_target,
          display_order: f.display_order,
        })),
        validation_rules: objectDetail.validation_rules || [],
        change_reason: changeReason,
      };

      await api.saveMetadataObject(payload);
      setMessage("Metadata schema updated and version incremented successfully.");
      setChangeReason("");
      await selectObject(objectDetail.object_type);
    } catch (err) {
      setError(err.message || "Failed to update metadata schema");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-400">Loading metadata schema studio...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            Metadata Configuration Studio
          </h2>
          <p className="text-xs text-slate-400">
            Configure dynamic entities, fields, lifecycles, and permissions without writing code.
          </p>
        </div>
      </div>

      {message && (
        <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Objects Selector (Left Sidebar) */}
        <div className="glass-card rounded-xl p-4 border border-slate-800 space-y-2">
          <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider mb-3 px-2">
            Configured Objects
          </h3>
          {objects.map((obj) => (
            <button
              key={obj.object_type}
              onClick={() => selectObject(obj.object_type)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-medium transition-all flex items-center justify-between ${
                selectedObjType === obj.object_type
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              <span>{obj.label}</span>
              <span className="text-[10px] opacity-75">v{obj.version}</span>
            </button>
          ))}
        </div>

        {/* Main Configuration Workspace */}
        {objectDetail && (
          <div className="md:col-span-3 space-y-6">
            <div className="glass-card rounded-xl p-6 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div>
                  <h3 className="text-base font-bold text-white">{objectDetail.label} Schema</h3>
                  <p className="text-xs text-slate-400 font-mono">Type: {objectDetail.object_type}</p>
                </div>
                <span className="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-mono">
                  Schema v{objectDetail.version}
                </span>
              </div>

              {/* Fields Table */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                  Configured Fields ({objectDetail.fields?.length || 0})
                </h4>
                <div className="overflow-x-auto rounded-lg border border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/80 text-slate-400 font-medium">
                      <tr>
                        <th className="py-2.5 px-3">Field Name</th>
                        <th className="py-2.5 px-3">Label</th>
                        <th className="py-2.5 px-3">Type</th>
                        <th className="py-2.5 px-3">Required</th>
                        <th className="py-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {(objectDetail.fields || []).map((f) => (
                        <tr key={f.name}>
                          <td className="py-2.5 px-3 font-mono text-indigo-400">{f.name}</td>
                          <td className="py-2.5 px-3 text-white">{f.label}</td>
                          <td className="py-2.5 px-3 text-slate-400">{f.type}</td>
                          <td className="py-2.5 px-3">
                            {f.required ? (
                              <span className="text-rose-400 font-semibold">Yes</span>
                            ) : (
                              <span className="text-slate-500">No</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => handleRemoveField(f.name)}
                              className="text-rose-400 hover:text-rose-300 text-[11px]"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Add New Field Row */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 space-y-3">
                <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Plus className="w-3.5 h-3.5 text-indigo-400" /> Add New Field to Schema
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                  <input
                    type="text"
                    value={newFieldName}
                    onChange={(e) => setNewFieldName(e.target.value)}
                    placeholder="field_key (e.g. tracking_id)"
                    className="px-3 py-1.5 rounded bg-slate-950 border border-slate-700 text-xs text-white"
                  />
                  <input
                    type="text"
                    value={newFieldLabel}
                    onChange={(e) => setNewFieldLabel(e.target.value)}
                    placeholder="Display Label"
                    className="px-3 py-1.5 rounded bg-slate-950 border border-slate-700 text-xs text-white"
                  />
                  <select
                    value={newFieldType}
                    onChange={(e) => setNewFieldType(e.target.value)}
                    className="px-3 py-1.5 rounded bg-slate-950 border border-slate-700 text-xs text-white"
                  >
                    <option value="text">text</option>
                    <option value="number">number</option>
                    <option value="date">date</option>
                    <option value="select">select</option>
                    <option value="checkbox">checkbox</option>
                  </select>
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newFieldRequired}
                        onChange={(e) => setNewFieldRequired(e.target.checked)}
                      />
                      Required
                    </label>
                    <button
                      type="button"
                      onClick={handleAddField}
                      className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>

              {/* Mandatory Governance Reason & Save */}
              <div className="pt-4 border-t border-slate-800 space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Mandatory Administrative Change Reason <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                    placeholder="e.g. Added tracking_id to satisfy Q4 compliance auditing guidelines..."
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="flex items-center justify-end">
                  <button
                    disabled={saving}
                    onClick={handleSaveSchema}
                    className="flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    {saving ? "Publishing Schema..." : "Publish Schema Changes"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
