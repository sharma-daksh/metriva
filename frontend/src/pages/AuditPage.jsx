import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAuditLog } from "../services/api";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export default function AuditPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAuditLog()
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 style={styles.h1}>Recovery Audit</h1>
      <p style={styles.subtitle}>Every recovery action taken, recorded — who, what, and the result.</p>

      {error && <p style={{ color: "#991b1b" }}>Failed to load audit log: {error}</p>}
      {loading ? (
        <p style={{ color: "#6b7280" }}>Loading…</p>
      ) : events.length === 0 ? (
        <p style={{ color: "#6b7280" }}>
          No recovery actions have been executed yet. Open an incident with a "retry" recommendation
          and click Execute Recovery.
        </p>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Time", "Incident", "Action", "Amount", "Decision", "Result", "Mode"].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i}>
                  <td style={styles.td}>{new Date(e.timestamp).toLocaleString()}</td>
                  <td style={styles.td}>
                    <Link to={`/incidents/${e.incident_id}`} style={styles.link}>{e.incident_id}</Link>
                  </td>
                  <td style={styles.td}>{e.action.replace(/_/g, " ")}</td>
                  <td style={styles.td}>{formatInr(e.amount)}</td>
                  <td style={styles.td}>{e.decision}</td>
                  <td style={{ ...styles.td, color: e.result === "SUCCESS" ? "#166534" : "#991b1b", fontWeight: 600 }}>
                    {e.result}
                  </td>
                  <td style={styles.td}><span style={styles.modeBadge}>{e.mode}</span></td>
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
  h1: { fontSize: "1.6rem", margin: 0, marginBottom: 4 },
  subtitle: { color: "#6b7280", fontSize: "0.9rem", marginBottom: 20 },
  tableWrap: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" },
  th: {
    textAlign: "left", padding: "10px 14px", backgroundColor: "#f9fafb",
    borderBottom: "1px solid #e5e7eb", fontWeight: 600, color: "#4b5563", fontSize: "0.75rem",
    textTransform: "uppercase", letterSpacing: "0.03em",
  },
  td: { padding: "10px 14px", borderBottom: "1px solid #f3f4f6" },
  link: { color: "#1d4ed8", textDecoration: "none", fontWeight: 600 },
  modeBadge: {
    fontSize: "0.68rem", fontWeight: 700, color: "#92400e", backgroundColor: "#fef3c7",
    padding: "2px 8px", borderRadius: 4,
  },
};