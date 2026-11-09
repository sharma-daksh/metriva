import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchIncident, fetchIncidentRootCause, fetchIncidentRecovery, executeRecovery } from "../services/api";
import { KpiCard, SeverityBadge, StatusBadge } from "../components/Cards";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const formatPct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

const TIMELINE_STAGES = ["WATCH", "ACTIVE", "RECOVERING", "RESOLVED"];

export default function IncidentDetailPage() {
  const { incidentId } = useParams();
  const [incident, setIncident] = useState(null);
  const [rootCause, setRootCause] = useState(null);
  const [recovery, setRecovery] = useState(null);
  const [error, setError] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [executeResult, setExecuteResult] = useState(null);

  useEffect(() => {
    fetchIncident(incidentId).then(setIncident).catch((e) => setError(e.message));
    fetchIncidentRootCause(incidentId).then(setRootCause).catch((e) => setError(e.message));
    fetchIncidentRecovery(incidentId).then(setRecovery).catch((e) => setError(e.message));
  }, [incidentId]);

  if (error) return <p style={{ color: "#991b1b" }}>Failed to load incident: {error}</p>;
  if (!incident) return <p style={{ color: "#6b7280" }}>Loading incident…</p>;

  const currentStageIdx = TIMELINE_STAGES.indexOf(incident.status);
  const excessPp = incident.incident_failure_rate != null && incident.baseline_failure_rate != null
    ? (incident.incident_failure_rate - incident.baseline_failure_rate) * 100
    : null;

  return (
    <div className="page-root page-incident-detail">
      <Link className="back-link" to="/incidents" style={styles.backLink}>← All incidents</Link>

      <div className="page-heading" style={styles.titleRow}>
        <div>
          <h1 className="page-title" style={styles.h1}>Payment Degradation</h1>
          <div style={styles.subtitle}>{incident.merchant_id} · {incident.incident_id}</div>
        </div>
        <div style={styles.badgeRow}>
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
        </div>
      </div>

      <div className="kpi-grid" style={styles.kpiRow}>
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

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Timeline</h2>
        <div className="incident-timeline" style={styles.timeline}>
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

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Revenue Impact</h2>
        <div className="revenue-grid" style={styles.revenueGrid}>
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

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Why is this happening?</h2>
        {!rootCause ? (
          <p style={{ color: "#6b7280" }}>Loading root-cause analysis…</p>
        ) : rootCause.dimensions.length === 0 ? (
          <p style={{ color: "#6b7280" }}>{rootCause.note || "Not enough evidence to attribute a cause."}</p>
        ) : (
          <>
            <p style={styles.rootCauseIntro}>
              We compare this merchant's normal failure rate against the incident period across five
              transaction attributes — network, receiving bank, device, customer state, and merchant
              category — to see which shifted the most.
            </p>
            <div className="dimension-list" style={styles.dimensionList}>
              {rootCause.dimensions.map((d) => (
                <div className="dimension-card" key={d.dimension} style={styles.dimensionCard}>
                  <div style={styles.dimensionRank}>
                    {d.rank === 1 ? "Primary factor" : d.rank === 2 ? "Secondary factor" : "Additional factor"}
                  </div>
                  <div style={styles.dimensionValue}>
                    {d.value} <span style={styles.dimensionLabel}>({d.dimension_label})</span>
                  </div>
                  <div style={styles.dimensionRates}>
                    Failure rate: {formatPct(d.baseline_failure_rate)} normally → {formatPct(d.incident_failure_rate)}
                    {" "}during this incident, across {d.incident_transactions} transactions
                  </div>
                </div>
              ))}
            </div>
            <p style={styles.note}>
              This shows correlated deterioration, not proven causality — these factors moved together
              with the incident, but that isn't the same as confirming what caused it.
            </p>
          </>
        )}
      </section>

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Revenue Recovery</h2>
        {!recovery ? (
          <p style={{ color: "#6b7280" }}>Loading recovery recommendation…</p>
        ) : (
          <>
            <div style={styles.recoveryHeader}>
              <span style={styles.recoveryAction}>{recovery.action.replace(/_/g, " ")}</span>
              {recovery.simulation && <span style={styles.simulationBadge}>SIMULATION</span>}
            </div>
            <p style={{ color: "#374151", fontSize: "0.88rem", marginTop: 4 }}>{recovery.reason}</p>

            {recovery.policy && (
              <div style={styles.policyBox}>
                <div style={styles.policyTitle}>Bounded policy</div>
                <ul style={styles.policyList}>
                  <li>Maximum retries: {recovery.policy.max_retries}</li>
                  <li>Cooldown: {recovery.policy.cooldown_minutes} minutes</li>
                  {recovery.policy.eligibility_rules.map((r) => <li key={r}>{r}</li>)}
                </ul>
              </div>
            )}

            {recovery.simulation && (
              <div className="sim-grid" style={styles.simGrid}>
                <div>
                  <div style={styles.revLabel}>Eligible</div>
                  <div style={styles.revValue}>{recovery.simulation.eligible_count}</div>
                </div>
                <div>
                  <div style={styles.revLabel}>Proposed retries</div>
                  <div style={styles.revValue}>{recovery.simulation.proposed_retries}</div>
                </div>
                <div>
                  <div style={styles.revLabel}>Projected recoverable</div>
                  <div style={styles.revValue}>{formatInr(recovery.simulation.projected_recoverable_amount)}</div>
                </div>
                <div>
                  <div style={styles.revLabel}>Successful recoveries</div>
                  <div style={{ ...styles.revValue, color: "#166534" }}>{recovery.simulation.successful_recoveries}</div>
                </div>
                <div>
                  <div style={styles.revLabel}>Recovered amount</div>
                  <div style={{ ...styles.revValue, color: "#166534" }}>{formatInr(recovery.simulation.recovered_amount)}</div>
                </div>
                <div>
                  <div style={styles.revLabel}>Failed retries / skipped</div>
                  <div style={styles.revValue}>{recovery.simulation.failed_retries} / {recovery.simulation.skipped}</div>
                </div>
              </div>
            )}

            {recovery.simulation && (
              <p style={styles.note}>
                Simulated — no live or test-mode payment API was called. Retry success is modeled at
                an assumed {formatPct(recovery.simulation.retry_success_probability_assumed)} probability per
                transaction, not a measured system property.
              </p>
            )}

            {recovery.simulation && (
              <div style={{ marginTop: 16 }}>
                <button
                  className="execute-btn"
                  style={{ ...styles.executeBtn, ...(executing ? styles.executeBtnDisabled : {}) }}
                  disabled={executing}
                  onClick={async () => {
                    setExecuting(true);
                    setExecuteResult(null);
                    try {
                      const result = await executeRecovery(incidentId);
                      setExecuteResult({ ok: true, ...result });
                    } catch (e) {
                      setExecuteResult({ ok: false, message: e.message });
                    } finally {
                      setExecuting(false);
                    }
                  }}
                >
                  {executing ? "Executing…" : "Execute Recovery"}
                </button>
                <span style={styles.executeNote}>Writes a record to the Audit Trail.</span>

                {executeResult && (
                  <p style={{
                    ...styles.note,
                    color: executeResult.ok ? "#166534" : "#991b1b",
                    marginTop: 10,
                  }}>
                    {executeResult.ok
                      ? `${executeResult.message} Recovered ${formatInr(executeResult.recovered_amount)} across ${executeResult.successful_recoveries} successful attempt(s).`
                      : executeResult.message}
                  </p>
                )}
              </div>
            )}
          </>
        )}
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
  rootCauseIntro: { fontSize: "0.85rem", color: "#4b5563", marginBottom: 16, lineHeight: 1.5 },
  dimensionList: { display: "flex", flexDirection: "column", gap: 10 },
  dimensionCard: {
    padding: "12px 16px", borderRadius: 8, border: "1px solid #f3f4f6", backgroundColor: "#fafafa",
  },
  dimensionRank: {
    fontSize: "0.68rem", fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase",
    color: "#dc2626", marginBottom: 4,
  },
  dimensionValue: { fontSize: "1rem", fontWeight: 700, color: "#111827" },
  dimensionLabel: { fontWeight: 400, color: "#9ca3af", fontSize: "0.85rem" },
  dimensionRates: { fontSize: "0.8rem", color: "#4b5563", marginTop: 4 },
  recoveryHeader: { display: "flex", alignItems: "center", gap: 10 },
  recoveryAction: { fontSize: "1rem", fontWeight: 700, textTransform: "capitalize", color: "#111827" },
  simulationBadge: {
    fontSize: "0.68rem", fontWeight: 700, letterSpacing: "0.05em", color: "#92400e",
    backgroundColor: "#fef3c7", padding: "2px 8px", borderRadius: 4,
  },
  policyBox: { backgroundColor: "#f9fafb", border: "1px solid #f0f0f0", borderRadius: 8, padding: "12px 16px", marginTop: 14 },
  policyTitle: { fontSize: "0.78rem", fontWeight: 700, color: "#6b7280", marginBottom: 6 },
  policyList: { margin: 0, paddingLeft: 18, fontSize: "0.8rem", color: "#374151", lineHeight: 1.6 },
  simGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, marginTop: 20 },
  executeBtn: {
    padding: "9px 18px", borderRadius: 8, border: "none", backgroundColor: "#0f172a",
    color: "white", fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
  },
  executeBtnDisabled: { opacity: 0.5, cursor: "not-allowed" },
  executeNote: { marginLeft: 10, fontSize: "0.78rem", color: "#9ca3af" },
};