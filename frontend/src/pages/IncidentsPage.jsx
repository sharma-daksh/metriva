import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchIncidents } from "../services/api";
import { SeverityBadge, StatusBadge } from "../components/Cards";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const formatPct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

const STATUS_FILTERS = ["ALL", "ACTIVE", "WATCH", "RECOVERING", "RESOLVED"];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState([]);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchIncidents(statusFilter === "ALL" ? {} : { status: statusFilter })
      .then(setIncidents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  return (
    <div>
      <div style={styles.headerRow}>
        <h1 style={styles.h1}>Incidents</h1>
        <div style={styles.filterRow}>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              style={{
                ...styles.filterBtn,
                ...(statusFilter === s ? styles.filterBtnActive : {}),
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {error && <p style={{ color: "#991b1b" }}>Failed to load incidents: {error}</p>}
      {loading ? (
        <p style={{ color: "#6b7280" }}>Loading incidents…</p>
      ) : incidents.length === 0 ? (
        <p style={{ color: "#6b7280" }}>No incidents match this filter.</p>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Incident", "Merchant", "Started", "Duration", "Severity", "Failure Increase", "Revenue at Risk", "Status"].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.incident_id}>
                  <td style={styles.td}>
                    <Link to={`/incidents/${inc.incident_id}`} style={styles.link}>{inc.incident_id}</Link>
                  </td>
                  <td style={styles.td}>{inc.merchant_id}</td>
                  <td style={styles.td}>{inc.start_date}</td>
                  <td style={styles.td}>{inc.duration_days}d</td>
                  <td style={styles.td}><SeverityBadge severity={inc.severity} /></td>
                  <td style={styles.td}>
                    {formatPct(inc.baseline_failure_rate)} → {formatPct(inc.incident_failure_rate)}
                  </td>
                  <td style={styles.td}>
                    {formatInr(inc.revenue_at_risk_low)}–{formatInr(inc.revenue_at_risk_high)}
                  </td>
                  <td style={styles.td}><StatusBadge status={inc.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles = {
  headerRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 },
  h1: { fontSize: "1.6rem", margin: 0 },
  filterRow: { display: "flex", gap: 6 },
  filterBtn: {
    padding: "6px 12px", borderRadius: 999, border: "1px solid #d1d5db",
    backgroundColor: "white", fontSize: "0.8rem", cursor: "pointer", color: "#374151",
  },
  filterBtnActive: { backgroundColor: "#0f172a", color: "white", borderColor: "#0f172a" },
  tableWrap: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" },
  th: {
    textAlign: "left", padding: "10px 14px", backgroundColor: "#f9fafb",
    borderBottom: "1px solid #e5e7eb", fontWeight: 600, color: "#4b5563", fontSize: "0.75rem",
    textTransform: "uppercase", letterSpacing: "0.03em",
  },
  td: { padding: "10px 14px", borderBottom: "1px solid #f3f4f6" },
  link: { color: "#1d4ed8", textDecoration: "none", fontWeight: 600 },
};
