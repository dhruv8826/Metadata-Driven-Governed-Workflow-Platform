const API_BASE = "http://localhost:8000/api";

export const getHeaders = () => {
  const tenantId = localStorage.getItem("active_tenant_id") || "procurement";
  const personaRole = localStorage.getItem("active_persona_role") || "Requester";
  const personaId = localStorage.getItem("active_persona_id") || "alice_req";

  return {
    "Content-Type": "application/json",
    "X-Tenant-Id": tenantId,
    "X-Persona-Role": personaRole,
    "X-Persona-Id": personaId,
  };
};

export const api = {
  // Tenants & Personas
  getTenants: async () => {
    const res = await fetch(`${API_BASE}/tenants`);
    return res.json();
  },
  getTenantPersonas: async (tenantId) => {
    const res = await fetch(`${API_BASE}/tenants/${tenantId}/personas`);
    return res.json();
  },

  // Metadata Studio
  getMetadataObjects: async () => {
    const res = await fetch(`${API_BASE}/metadata/objects`, { headers: getHeaders() });
    return res.json();
  },
  getMetadataObject: async (objectType) => {
    const res = await fetch(`${API_BASE}/metadata/objects/${objectType}`, { headers: getHeaders() });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load metadata");
    return res.json();
  },
  saveMetadataObject: async (payload) => {
    const res = await fetch(`${API_BASE}/metadata/objects`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to save metadata");
    return data;
  },

  // Records CRUD
  getRecords: async (objectType, params = {}) => {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`${API_BASE}/records/${objectType}${query ? `?${query}` : ""}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load records");
    return res.json();
  },
  getRecordDetail: async (objectType, recordId) => {
    const res = await fetch(`${API_BASE}/records/${objectType}/${recordId}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load record");
    return res.json();
  },
  createRecord: async (objectType, data) => {
    const res = await fetch(`${API_BASE}/records/${objectType}`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ data }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || "Failed to create record");
    return json;
  },
  updateRecord: async (objectType, recordId, data) => {
    const res = await fetch(`${API_BASE}/records/${objectType}/${recordId}`, {
      method: "PUT",
      headers: getHeaders(),
      body: JSON.stringify({ data }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || "Failed to update record");
    return json;
  },
  deleteRecord: async (objectType, recordId) => {
    const res = await fetch(`${API_BASE}/records/${objectType}/${recordId}`, {
      method: "DELETE",
      headers: getHeaders(),
    });
    return res.json();
  },

  // Lifecycle Transitions
  triggerTransition: async (recordId, transitionName) => {
    const res = await fetch(`${API_BASE}/records/${recordId}/transitions`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ transition_name: transitionName }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Transition failed");
    return data;
  },

  // Approvals Broker
  getPendingApprovals: async () => {
    const res = await fetch(`${API_BASE}/approvals/pending`, { headers: getHeaders() });
    return res.json();
  },
  submitApprovalDecision: async (approvalId, decision, reason) => {
    const res = await fetch(`${API_BASE}/approvals/${approvalId}/decision`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ decision, reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to process decision");
    return data;
  },

  // Dashboards & Aggregations
  getDashboards: async () => {
    const res = await fetch(`${API_BASE}/dashboards`, { headers: getHeaders() });
    return res.json();
  },
  getDashboardMetrics: async (dashboardId) => {
    const res = await fetch(`${API_BASE}/dashboards/${dashboardId}`, { headers: getHeaders() });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to fetch dashboard metrics");
    return res.json();
  },

  // Audit Trail
  getAuditTrail: async (params = {}) => {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`${API_BASE}/audit${query ? `?${query}` : ""}`, {
      headers: getHeaders(),
    });
    return res.json();
  },
};
