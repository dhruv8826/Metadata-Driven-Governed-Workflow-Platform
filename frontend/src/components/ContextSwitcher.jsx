import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { Building2, UserCircle, Shield } from "lucide-react";

export default function ContextSwitcher({ onContextChange }) {
  const [tenants, setTenants] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [activeTenant, setActiveTenant] = useState(
    localStorage.getItem("active_tenant_id") || "procurement"
  );
  const [activePersonaId, setActivePersonaId] = useState(
    localStorage.getItem("active_persona_id") || "alice_req"
  );
  const [activeRole, setActiveRole] = useState(
    localStorage.getItem("active_persona_role") || "Requester"
  );
  const [activeName, setActiveName] = useState(
    localStorage.getItem("active_persona_name") || "Alice Johnson"
  );

  useEffect(() => {
    loadTenantsAndPersonas(activeTenant);
  }, []);

  const loadTenantsAndPersonas = async (tenantId) => {
    try {
      const tenantList = await api.getTenants();
      setTenants(tenantList);

      const personaData = await api.getTenantPersonas(tenantId);
      const personaList = personaData.personas || [];
      setPersonas(personaList);

      // If current persona not in tenant, select first
      const currentExists = personaList.find((p) => p.id === activePersonaId);
      if (!currentExists && personaList.length > 0) {
        selectPersona(personaList[0], tenantId);
      }
    } catch (err) {
      console.error("Failed to load context:", err);
    }
  };

  const handleTenantChange = async (e) => {
    const newTenantId = e.target.value;
    setActiveTenant(newTenantId);
    localStorage.setItem("active_tenant_id", newTenantId);

    const personaData = await api.getTenantPersonas(newTenantId);
    const personaList = personaData.personas || [];
    setPersonas(personaList);

    if (personaList.length > 0) {
      selectPersona(personaList[0], newTenantId);
    }
  };

  const selectPersona = (persona, tenantId = activeTenant) => {
    setActivePersonaId(persona.id);
    setActiveRole(persona.role);
    setActiveName(persona.name);
    localStorage.setItem("active_tenant_id", tenantId);
    localStorage.setItem("active_persona_id", persona.id);
    localStorage.setItem("active_persona_role", persona.role);
    localStorage.setItem("active_persona_name", persona.name);
    if (onContextChange) {
      onContextChange({ tenantId, persona });
    }
  };

  const handlePersonaSelect = (e) => {
    const selected = personas.find((p) => p.id === e.target.value);
    if (selected) {
      selectPersona(selected);
    }
  };

  const getRoleBadgeColor = (role) => {
    switch (role?.toLowerCase()) {
      case "admin":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "director":
      case "facilities lead":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "manager":
        return "bg-indigo-50 text-indigo-700 border-indigo-200";
      case "finance":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-slate-200 px-6 py-3 sticky top-0 z-50 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Brand Title */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-600/20">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              GovFlow
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium">
                Metadata Driven
              </span>
            </h1>
            <p className="text-xs text-slate-500">Governed Multi-Tenant Workflow Platform</p>
          </div>
        </div>

        {/* Omnipresent Tenant & Persona Switcher */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Tenant Selector */}
          <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 shadow-sm">
            <Building2 className="w-4 h-4 text-indigo-600" />
            <span className="text-xs text-slate-500 font-medium">Tenant:</span>
            <select
              value={activeTenant}
              onChange={handleTenantChange}
              className="bg-transparent text-xs text-slate-800 font-semibold focus:outline-none cursor-pointer"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id} className="bg-white text-slate-900">
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Persona Switcher */}
          <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 shadow-sm">
            <UserCircle className="w-4 h-4 text-violet-600" />
            <span className="text-xs text-slate-500 font-medium">Persona:</span>
            <select
              value={activePersonaId}
              onChange={handlePersonaSelect}
              className="bg-transparent text-xs text-slate-800 font-semibold focus:outline-none cursor-pointer"
            >
              {personas.map((p) => (
                <option key={p.id} value={p.id} className="bg-white text-slate-900">
                  {p.name} ({p.role})
                </option>
              ))}
            </select>
          </div>

          {/* Active Role Pill */}
          <div
            className={`text-xs px-2.5 py-1 rounded-md border font-semibold flex items-center gap-1.5 shadow-sm ${getRoleBadgeColor(
              activeRole
            )}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
            Role: {activeRole}
          </div>
        </div>
      </div>
    </header>
  );
}
