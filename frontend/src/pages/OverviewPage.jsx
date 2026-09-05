import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  fetchMerchants, fetchMerchantDailyMetrics, fetchIncidentsSummary, fetchIncidents,
} from "../services/api";
import { KpiCard, SeverityBadge, StatusBadge } from "../components/Cards";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const formatPct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

export default function OverviewPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [dailyMetrics, setDailyMetrics] = useState([]);
  const [summary, setSummary] = useState(null);
  const [openAlerts, setOpenAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([fetchMerchants(), fetchIncidentsSummary(), fetchIncidents({ status: "ACTIVE" })])
      .then(([merchantList, summaryData, activeIncidents]) => {
        setMerchants(merchantList);
        setSummary(summaryData);
        setOpenAlerts(activeIncidents.slice(0, 5));
        if (merchantList.length > 0) {
          const riskiest = [...merchantList].sort((a, b) => b.failure_rate - a.failure_rate)[0];
          setSelectedMerchant(riskiest.merchant_id);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedMerchant) return;
    fetchMerchantDailyMetrics(selectedMerchant)
      .then(setDailyMetrics)
      .catch((e) => setError(e.message));
  }, [selectedMerchant]);

  const chartData = useMemo(
    () =>
      dailyMetrics.map((d) => ({
        date: d.date.slice(5), // MM-DD
        "Failure rate %": d.failure_rate != null ? +(d.failure_rate * 100).toFixed(2) : null,
      })),
    [dailyMetrics]
  );

  const selectedMerchantData = merchants.find((m) => m.merchant_id === selectedMerchant);

  if (loading) return <p style={{ color: "#6b7280" }}>Loading portfolio data…</p>;
  if (error) return <p style={{ color: "#991b1b" }}>Failed to load dashboard: {error}</p>;

  return (
    <div>
      <div style={styles.headerRow}>
        <h1 style={styles.h1}>Overview</h1>
        <select
          value={selectedMerchant || ""}
          onChange={(e) => setSelectedMerchant(e.target.value)}
          style={styles.select}
        >
          {merchants.map((m) => (
            <option key={m.merchant_id} value={m.merchant_id}>
              {m.merchant_id} {m.open_incidents > 0 ? `(${m.open_incidents} open)` : ""}
            </option>
          ))}
        </select>
      </div>

      <div style={styles.kpiRow}>
        <KpiCard
          label="Merchant Health"
          value={selectedMerchantData ? `${selectedMerchantData.health_score}/100` : "—"}
        />
        <KpiCard
          label="Failure Rate"
          value={selectedMerchantData ? formatPct(selectedMerchantData.failure_rate) : "—"}
        />
        <KpiCard
          label="Transaction Volume"
          value={selectedMerchantData ? formatInr(selectedMerchantData.transaction_volume) : "—"}
        />
        <KpiCard
          label="Portfolio Revenue at Risk"
          tone="danger"
          value={
            summary
              ? `${formatInr(summary.total_revenue_at_risk_low)}–${formatInr(summary.total_revenue_at_risk_high)}`
              : "—"
          }
          sub={summary ? `${summary.open_incidents} open incidents` : undefined}
        />
      </div>

      <section style={styles.section}>
        <h2 style={styles.h2}>Payment Health — {selectedMerchant}</h2>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip />
              <Line type="monotone" dataKey="Failure rate %" stroke="#dc2626" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>Active Alerts</h2>
        {openAlerts.length === 0 ? (
          <p style={{ color: "#6b7280" }}>No active incidents right now.</p>
        ) : (
          <div style={styles.alertList}>
            {openAlerts.map((inc) => (
              <Link to={`/incidents/${inc.incident_id}`} key={inc.incident_id} style={styles.alertCard}>
                <div style={styles.alertTop}>
                  <SeverityBadge severity={inc.severity} />
                  <StatusBadge status={inc.status} />
                  <span style={styles.alertMerchant}>{inc.merchant_id}</span>
                </div>
                <div style={styles.alertBody}>
                  Failure rate {formatPct(inc.baseline_failure_rate)} → {formatPct(inc.incident_failure_rate)}
                  {" · "}Revenue at risk {formatInr(inc.revenue_at_risk_low)}–{formatInr(inc.revenue_at_risk_high)}
                </div>
                <div style={styles.alertMeta}>
                  {inc.start_date} → {inc.end_date} ({inc.duration_days}d)
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

const styles = {
  headerRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 },
  h1: { fontSize: "1.6rem", margin: 0 },
  h2: { fontSize: "1.05rem", marginBottom: 12 },
  select: { padding: "8px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: "0.9rem" },
  kpiRow: { display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 28 },
  section: {
    backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10,
    padding: 20, marginBottom: 20,
  },
  alertList: { display: "flex", flexDirection: "column", gap: 10 },
  alertCard: {
    display: "block", padding: "12px 14px", borderRadius: 8, border: "1px solid #f3f4f6",
    textDecoration: "none", color: "inherit",
  },
  alertTop: { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 },
  alertMerchant: { fontWeight: 600, fontSize: "0.85rem", color: "#111827" },
  alertBody: { fontSize: "0.85rem", color: "#374151" },
  alertMeta: { fontSize: "0.75rem", color: "#9ca3af", marginTop: 4 },
};
