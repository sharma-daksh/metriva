import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchIncident } from "../services/api";
import { KpiCard, SeverityBadge, StatusBadge } from "../components/Cards";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const formatPct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

const TIMELINE_STAGES = ["WATCH", "ACTIVE", "RECOVERING", "RESOLVED"];

export default function IncidentDetailPage() {
  const { incidentId } = useParams();
  const [incident, setIncident] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchIncident(incidentId).then(setIncident).catch((e) => setError(e.message));
  }, [incidentId]);

  if (error) return <p style={{ color: "#991b1b" }}>Failed to load incident: {error}</p>;
  if (!incident) return <p style={{ color: "#6b7280" }}>Loading incident…</p>;

  const currentStageIdx = TIMELINE_STAGES.indexOf(incident.status);
  const excessPp = incident.incident_failure_rate != null && incident.baseline_failure_rate != null
    ? (incident.incident_failure_rate - incident.baseline_failure_rate) * 100
    : null;

  return (
    <div>
      <Link to="/incidents" style={styles.backLink}>← All incidents</Link>

      <div style={styles.titleRow}>
        <div>
          <h1 style={styles.h1}>Payment Degradation</h1>
          <div style={styles.subtitle}>{incident.merchant_id} · {incident.incident_id}</div>
        </div>
        <div style={styles.badgeRow}>
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
        </div>
      </div>

      <div style={styles.kpiRow}>
        <KpiCard label="Baseline Failure Rate" value={formatPct(incident.baseline_failure_rate)} />
        <KpiCard
          label="Incident Failure Rate"
          value={formatPct(incident.incident_failure_rate)}
          sub={excessPp != null ? `+${excessPp.toFixed(1)} pp` : undefined}
          tone="warning"
        />
        <KpiCard
          label="Revenue at Risk"
          value={`${formatInr(incident.revenue_at_risk_low)}–${formatInr(incident.revenue_at_risk_high)}`}
          tone="danger"
        />
        <KpiCard label="Confidence" value={formatPct(incident.confidence)} />
      </div>

      <section style={styles.section}>
        <h2 style={styles.h2}>Timeline</h2>
        <div style={styles.timeline}>
          {TIMELINE_STAGES.map((stage, i) => (
            <div key={stage} style={styles.timelineStep}>
              <div
                style={{
                  ...styles.timelineDot,
                  ...(i <= currentStageIdx ? styles.timelineDotActive : {}),
                }}
              />
              <div style={styles.timelineLabel}>{stage}</div>
              {i < TIMELINE_STAGES.length - 1 && (
                <div
                  style={{
                    ...styles.timelineLine,
                    ...(i < currentStageIdx ? styles.timelineLineActive : {}),
                  }}
                />
              )}
            </div>
          ))}
        </div>
        <p style={styles.timelineMeta}>
          Detected {incident.detection_date} ({incident.detection_delay_days}d after onset {incident.start_date}) ·
          {" "}spans {incident.start_date} → {incident.end_date} ({incident.duration_days} days) ·
          {" "}peak failure rate {formatPct(incident.peak_failure_rate)}
        </p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>Revenue Impact</h2>
        <div style={styles.revenueGrid}>
          <div>
            <div style={styles.revLabel}>Failed transactions</div>
            <div style={styles.revValue}>{incident.failed_transactions}</div>
          </div>
          <div>
            <div style={styles.revLabel}>Excess failures (above baseline)</div>
            <div style={styles.revValue}>{incident.excess_failures}</div>
          </div>
          <div>
            <div style={styles.revLabel}>Estimated revenue at risk</div>
            <div style={styles.revValue}>
              {formatInr(incident.revenue_at_risk_low)} – {formatInr(incident.revenue_at_risk_high)}
            </div>
          </div>
        </div>
        <p style={styles.note}>
          Estimated as excess failures (observed minus expected under baseline) × average transaction
          value, with a ±15% uncertainty band — not the value of every failed transaction.
        </p>
      </section>
    </div>
  );
}

const styles = {
  backLink: { color: "#6b7280", fontSize: "0.85rem", textDecoration: "none", display: "inline-block", marginBottom: 16 },
  titleRow: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 },
  h1: { fontSize: "1.5rem", margin: 0 },
  subtitle: { color: "#6b7280", fontSize: "0.9rem", marginTop: 2 },
  badgeRow: { display: "flex", gap: 8, alignItems: "center" },
  kpiRow: { display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 24 },
  section: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 20, marginBottom: 20 },
  h2: { fontSize: "1.05rem", marginBottom: 16 },
  timeline: { display: "flex", alignItems: "center" },
  timelineStep: { display: "flex", alignItems: "center", flex: 1, position: "relative" },
  timelineDot: {
    width: 16, height: 16, borderRadius: "50%", backgroundColor: "#e5e7eb",
    border: "2px solid #e5e7eb", flexShrink: 0, zIndex: 1,
  },
  timelineDotActive: { backgroundColor: "#dc2626", borderColor: "#dc2626" },
  timelineLabel: {
    position: "absolute", top: 22, left: 0, fontSize: "0.7rem", color: "#6b7280",
    whiteSpace: "nowrap", transform: "translateX(-25%)",
  },
  timelineLine: { flex: 1, height: 2, backgroundColor: "#e5e7eb" },
  timelineLineActive: { backgroundColor: "#dc2626" },
  timelineMeta: { fontSize: "0.8rem", color: "#6b7280", marginTop: 32 },
  revenueGrid: { display: "flex", gap: 32, flexWrap: "wrap" },
  revLabel: { fontSize: "0.78rem", color: "#6b7280" },
  revValue: { fontSize: "1.2rem", fontWeight: 700, marginTop: 4 },
  note: { fontSize: "0.78rem", color: "#9ca3af", marginTop: 16 },
};
