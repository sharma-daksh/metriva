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
