import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import { Save, AlertCircle, X } from "lucide-react";

export default function DynamicForm({ objectMeta, initialData = {}, onSubmit, onCancel }) {
  const [formData, setFormData] = useState(initialData);
  const [referenceOptions, setReferenceOptions] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const fields = objectMeta?.fields || [];
  // Only display editable fields on create/edit
  const editableFields = fields.filter((f) => f.can_edit !== false);

  useEffect(() => {
    // Load options for reference fields
    const loadReferences = async () => {
      const refMap = {};
      for (const field of fields) {
        if (field.type === "reference" && field.reference_target) {
          try {
            const res = await api.getRecords(field.reference_target, { limit: 50 });
            refMap[field.name] = res.items || [];
          } catch (err) {
            console.error(`Failed to load references for ${field.name}:`, err);
          }
        }
      }
      setReferenceOptions(refMap);
    };
    loadReferences();
  }, [objectMeta]);

  const handleChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit(formData);
    } catch (err) {
      setError(err.message || "Failed to submit form");
    } finally {
      setSubmitting(false);
    }
  };

  const isFieldVisible = (field) => {
    if (!field.conditional_visibility) return true;
    const { field: depField, operator, value: targetVal } = field.conditional_visibility;
    const currentVal = formData[depField];
    if (operator === "==" || operator === "eq") return currentVal === targetVal;
    if (operator === "!=" || operator === "ne") return currentVal !== targetVal;
    if (operator === ">") return Number(currentVal) > Number(targetVal);
    if (operator === ">=") return Number(currentVal) >= Number(targetVal);
    if (operator === "<") return Number(currentVal) < Number(targetVal);
    if (operator === "<=") return Number(currentVal) <= Number(targetVal);
    if (operator === "truthy") return Boolean(currentVal);
    return true;
  };

  return (
    <div className="glass-card rounded-xl p-6 border border-slate-800">
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-800">
        <div>
          <h3 className="text-lg font-semibold text-white">
            {initialData && Object.keys(initialData).length > 0
              ? `Edit ${objectMeta.label}`
              : `New ${objectMeta.label}`}
          </h3>
          <p className="text-xs text-slate-400">
            Rendered dynamically from schema metadata (v{objectMeta.version})
          </p>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Validation & Rule Guardrail Error</p>
            <p className="text-xs mt-0.5 text-rose-300">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {editableFields.map((field) => {
            if (!isFieldVisible(field)) return null;
            const value = formData[field.name] ?? "";

            return (
              <div
                key={field.name}
                className={field.type === "text" && field.name === "justification" ? "md:col-span-2" : ""}
              >
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  {field.label}
                  {field.required && <span className="text-rose-400 ml-1">*</span>}
                  {field.read_only && <span className="text-slate-500 ml-1 text-[10px]">(Read-only)</span>}
                </label>

                {field.type === "text" && (
                  <input
                    type="text"
                    required={field.required}
                    disabled={field.read_only}
                    value={value}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    placeholder={`Enter ${field.label.toLowerCase()}`}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                  />
                )}

                {field.type === "number" && (
                  <input
                    type="number"
                    step="any"
                    required={field.required}
                    disabled={field.read_only}
                    value={value}
                    onChange={(e) => handleChange(field.name, parseFloat(e.target.value) || 0)}
                    placeholder="0.00"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                  />
                )}

                {field.type === "date" && (
                  <input
                    type="date"
                    required={field.required}
                    disabled={field.read_only}
                    value={value}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                  />
                )}

                {field.type === "checkbox" && (
                  <div className="flex items-center gap-2 pt-1.5">
                    <input
                      type="checkbox"
                      id={`field_${field.name}`}
                      disabled={field.read_only}
                      checked={Boolean(formData[field.name])}
                      onChange={(e) => handleChange(field.name, e.target.checked)}
                      className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer disabled:opacity-50"
                    />
                    <label htmlFor={`field_${field.name}`} className="text-xs text-slate-300 cursor-pointer select-none">
                      {field.placeholder || `Enable ${field.label}`}
                    </label>
                  </div>
                )}

                {field.type === "select" && (
                  <select
                    required={field.required}
                    disabled={field.read_only}
                    value={value}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                  >
                    <option value="">Select an option</option>
                    {(field.options || []).map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                )}

                {field.type === "reference" && (
                  <select
                    required={field.required}
                    disabled={field.read_only}
                    value={value}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                  >
                    <option value="">Select {field.label}</option>
                    {(referenceOptions[field.name] || []).map((refRec) => {
                      const displayTitle =
                        refRec.data?.name || refRec.data?.code || refRec.id;
                      return (
                        <option key={refRec.id} value={refRec.id}>
                          {displayTitle} ({refRec.id})
                        </option>
                      );
                    })}
                  </select>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-800">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-sm font-medium text-white shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {submitting ? "Saving..." : "Save Record"}
          </button>
        </div>
      </form>
    </div>
  );
}
