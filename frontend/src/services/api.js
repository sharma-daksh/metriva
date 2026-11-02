const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

/**
 * Checks backend liveness. Used on the landing page in Phase 1 to prove the
 * frontend and backend can talk to each other before any real features exist.
 */
export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function fetchMerchants() {
  const response = await fetch(`${API_BASE_URL}/merchants`);
  if (!response.ok) throw new Error(`Failed to load merchants (${response.status})`);
  return response.json();
}

export async function fetchMerchant(merchantId) {
  const response = await fetch(`${API_BASE_URL}/merchants/${merchantId}`);
  if (!response.ok) throw new Error(`Failed to load merchant ${merchantId} (${response.status})`);
  return response.json();
}

export async function fetchMerchantDailyMetrics(merchantId) {
  const response = await fetch(`${API_BASE_URL}/merchants/${merchantId}/daily-metrics`);
  if (!response.ok) {
    throw new Error(`Failed to load daily metrics for ${merchantId} (${response.status})`);
  }
  return response.json();
}

export async function fetchIncidents({ merchantId, status } = {}) {
  const params = new URLSearchParams();
  if (merchantId) params.set("merchant_id", merchantId);
  if (status) params.set("status", status);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/incidents${query}`);
  if (!response.ok) throw new Error(`Failed to load incidents (${response.status})`);
  return response.json();
}

export async function fetchIncidentsSummary() {
  const response = await fetch(`${API_BASE_URL}/incidents/summary`);
  if (!response.ok) throw new Error(`Failed to load incident summary (${response.status})`);
  return response.json();
}

export async function fetchIncident(incidentId) {
  const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}`);
  if (!response.ok) throw new Error(`Failed to load incident ${incidentId} (${response.status})`);
  return response.json();
}

export async function fetchIncidentRootCause(incidentId) {
  const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/root-cause`);
  if (!response.ok) throw new Error(`Failed to load root cause for ${incidentId} (${response.status})`);
  return response.json();
}

export async function fetchMerchantAnalytics(merchantId, { startDate, endDate } = {}) {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/merchants/${merchantId}/analytics${query}`);
  if (!response.ok) throw new Error(`Failed to load analytics for ${merchantId} (${response.status})`);
  return response.json();
}

export async function fetchIncidentRecovery(incidentId) {
  const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/recovery`);
  if (!response.ok) throw new Error(`Failed to load recovery info for ${incidentId} (${response.status})`);
  return response.json();
}

async function _throwWithDetail(response) {
  let detail = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    if (body?.detail) detail = body.detail;
  } catch {
    // response wasn't JSON — keep the generic message
  }
  throw new Error(detail);
}

export async function previewUpload(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/upload/preview`, { method: "POST", body: formData });
  if (!response.ok) await _throwWithDetail(response);
  return response.json();
}

export async function commitUpload(file, mapping) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mapping", JSON.stringify(mapping));
  const response = await fetch(`${API_BASE_URL}/upload/commit`, { method: "POST", body: formData });
  if (!response.ok) await _throwWithDetail(response);
  return response.json();
}

export async function fetchUploadStatus() {
  const response = await fetch(`${API_BASE_URL}/upload/status`);
  if (!response.ok) throw new Error(`Failed to load dataset status (${response.status})`);
  return response.json();
}

export async function fetchAuditLog({ incidentId, merchantId } = {}) {
  const params = new URLSearchParams();
  if (incidentId) params.set("incident_id", incidentId);
  if (merchantId) params.set("merchant_id", merchantId);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/audit${query}`);
  if (!response.ok) throw new Error(`Failed to load audit log (${response.status})`);
  return response.json();
}

export async function executeRecovery(incidentId) {
  const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/recovery/execute`, { method: "POST" });
  if (!response.ok) await _throwWithDetail(response);
  return response.json();
}

export async function resetToDemo() {
  const response = await fetch(`${API_BASE_URL}/upload/reset-to-demo`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed to reset to demo (${response.status})`);
  return response.json();
}