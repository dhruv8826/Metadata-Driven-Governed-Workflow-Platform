import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { Building2, UserCircle, Shield, RefreshCw } from "lucide-react";

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
        return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      case "director":
      case "facilities lead":
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "manager":
        return "bg-indigo-500/20 text-indigo-400 border-indigo-500/30";
      case "finance":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      default:
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    }
  };

  return (
    <header className="glass-panel border-b border-slate-800 px-6 py-3 sticky top-0 z-50">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Brand Title */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
              GovFlow
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-normal">
                Metadata Driven
              </span>
            </h1>
            <p className="text-xs text-slate-400">Governed Multi-Tenant Workflow Platform</p>
          </div>
        </div>

        {/* Omnipresent Tenant & Persona Switcher */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Tenant Selector */}
          <div className="flex items-center gap-2 bg-slate-950/60 px-3 py-1.5 rounded-lg border border-slate-800">
            <Building2 className="w-4 h-4 text-indigo-400" />
            <span className="text-xs text-slate-400 font-medium">Tenant:</span>
            <select
              value={activeTenant}
              onChange={handleTenantChange}
              className="bg-transparent text-xs text-white font-medium focus:outline-none cursor-pointer"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id} className="bg-slate-900 text-white">
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Persona Switcher */}
          <div className="flex items-center gap-2 bg-slate-950/60 px-3 py-1.5 rounded-lg border border-slate-800">
            <UserCircle className="w-4 h-4 text-violet-400" />
            <span className="text-xs text-slate-400 font-medium">Persona:</span>
            <select
              value={activePersonaId}
              onChange={handlePersonaSelect}
              className="bg-transparent text-xs text-white font-medium focus:outline-none cursor-pointer"
            >
              {personas.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                  {p.name} ({p.role})
                </option>
              ))}
            </select>
          </div>

          {/* Active Role Pill */}
          <div
            className={`text-xs px-2.5 py-1 rounded-md border font-semibold flex items-center gap-1.5 ${getRoleBadgeColor(
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
