import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { fetchMerchants, fetchMerchantAnalytics } from "../services/api";

const formatInr = (n) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const DATE_PRESETS = [
  { label: "All time", days: null },
  { label: "Last 90 days", days: 90 },
  { label: "Last 30 days", days: 30 },
];

const DATASET_END_DATE = "2024-12-31"; // this dataset's last day — presets are relative to it, not "today"

function presetToRange(days) {
  if (days == null) return { startDate: null, endDate: null };
  const end = new Date(DATASET_END_DATE);
  const start = new Date(end);
  start.setDate(start.getDate() - days + 1);
  return { startDate: start.toISOString().slice(0, 10), endDate: DATASET_END_DATE };
}

const BAR_COLOR = "#2563eb";
const WORST_COLOR = "#dc2626";

function DimensionBarChart({ title, data }) {
  if (!data || data.values.length === 0) return null;
  const chartData = data.values.map((v) => ({
    name: v.value,
    "Failure rate %": +(v.failure_rate * 100).toFixed(2),
    transactions: v.transaction_count,
  }));
  const maxRate = Math.max(...chartData.map((d) => d["Failure rate %"]));

  return (
    <div className="chart-card" style={styles.chartCard}>
      <h3 style={styles.chartTitle}>{data.label}</h3>
      <div style={{ width: "100%", height: 200 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
            <YAxis tick={{ fontSize: 10 }} unit="%" />
            <Tooltip
              formatter={(value, name) => [name === "Failure rate %" ? `${value}%` : value, name]}
            />
            <Bar dataKey="Failure rate %" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry["Failure rate %"] === maxRate ? WORST_COLOR : BAR_COLOR} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [datePreset, setDatePreset] = useState(DATE_PRESETS[0]);

  useEffect(() => {
    fetchMerchants()
      .then((list) => {
        setMerchants(list);
        if (list.length > 0) setSelectedMerchant(list[0].merchant_id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedMerchant) return;
    const range = presetToRange(datePreset.days);
    fetchMerchantAnalytics(selectedMerchant, range).then(setAnalytics).catch((e) => setError(e.message));
  }, [selectedMerchant, datePreset]);

  const dailyChartData = useMemo(
    () =>
      (analytics?.daily || []).map((d) => ({
        date: d.date.slice(5),
        "Failure rate %": +(d.failure_rate * 100).toFixed(2),
        "Transaction volume": Math.round(d.transaction_volume),
        "Avg transaction value": Math.round(d.average_transaction_value),
      })),
    [analytics]
  );

  const totals = useMemo(() => {
    if (!analytics?.daily?.length) return null;
    const volume = analytics.daily.reduce((s, d) => s + d.transaction_volume, 0);
    const failedAmount = analytics.daily.reduce((s, d) => s + d.failed_amount, 0);
    const txCount = analytics.daily.reduce((s, d) => s + d.transaction_count, 0);
    const failCount = analytics.daily.reduce((s, d) => s + d.failure_count, 0);
    return { volume, failedAmount, txCount, failCount, failRate: txCount ? failCount / txCount : 0 };
  }, [analytics]);

  if (loading) return <p style={{ color: "#6b7280" }}>Loading merchants…</p>;
  if (error) return <p style={{ color: "#991b1b" }}>Failed to load analytics: {error}</p>;

  return (
    <div className="page-root page-analytics">
      <div className="page-heading" style={styles.headerRow}>
        <h1 className="page-title" style={styles.h1}>Payment Analytics</h1>
        <div className="analytics-controls" style={styles.controls}>
          <div className="date-preset-row" style={styles.presetRow}>
            {DATE_PRESETS.map((preset) => (
              <button
                key={preset.label}
                onClick={() => setDatePreset(preset)}
                style={{
                  ...styles.presetBtn,
                  ...(datePreset.label === preset.label ? styles.presetBtnActive : {}),
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <select
            value={selectedMerchant || ""}
            onChange={(e) => setSelectedMerchant(e.target.value)}
            style={styles.select}
          >
            {merchants.map((m) => (
              <option key={m.merchant_id} value={m.merchant_id}>{m.merchant_id}</option>
            ))}
          </select>
        </div>
      </div>

      {totals && (
        <div className="kpi-grid" style={styles.kpiRow}>
          <div style={styles.kpiCard}>
            <div style={styles.kpiLabel}>GMV / Payment Volume</div>
            <div style={styles.kpiValue}>{formatInr(totals.volume)}</div>
          </div>
          <div style={styles.kpiCard}>
            <div style={styles.kpiLabel}>Transactions</div>
            <div style={styles.kpiValue}>{totals.txCount.toLocaleString("en-IN")}</div>
          </div>
          <div style={styles.kpiCard}>
            <div style={styles.kpiLabel}>Overall Failure Rate</div>
            <div style={styles.kpiValue}>{(totals.failRate * 100).toFixed(1)}%</div>
          </div>
          <div style={styles.kpiCard}>
            <div style={styles.kpiLabel}>Failed Payment Amount</div>
            <div style={{ ...styles.kpiValue, color: "#dc2626" }}>{formatInr(totals.failedAmount)}</div>
          </div>
        </div>
      )}

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Failure Rate Over Time</h2>
        <div style={{ width: "100%", height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={dailyChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip />
              <Line type="monotone" dataKey="Failure rate %" stroke="#dc2626" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel-card" style={styles.section}>
        <h2 style={styles.h2}>Transaction Volume Over Time</h2>
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={dailyChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => formatInr(v)} />
              <Line type="monotone" dataKey="Transaction volume" stroke="#2563eb" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {analytics && (
        <section className="panel-card" style={styles.section}>
          <h2 style={styles.h2}>Failure Rate by Attribute</h2>
          <p style={styles.subnote}>Red bar marks the worst-performing value in each attribute.</p>
          <div style={styles.chartGrid}>
            <DimensionBarChart data={analytics.breakdowns.receiver_bank} />
            <DimensionBarChart data={analytics.breakdowns.network_type} />
            <DimensionBarChart data={analytics.breakdowns.device_type} />
            <DimensionBarChart data={analytics.breakdowns.state} />
            <DimensionBarChart data={analytics.breakdowns.merchant_category} />
            <DimensionBarChart data={analytics.breakdowns.day_of_week} />
          </div>
          <div style={{ marginTop: 20 }}>
            <DimensionBarChart data={analytics.breakdowns.hour} />
          </div>
        </section>
      )}
    </div>
  );
}

const styles = {
  headerRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 },
  controls: { display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" },
  presetRow: { display: "flex", gap: 6 },
  presetBtn: {
    padding: "6px 12px", borderRadius: 999, border: "1px solid #d1d5db",
    backgroundColor: "white", fontSize: "0.8rem", cursor: "pointer", color: "#374151",
  },
  presetBtnActive: { backgroundColor: "#0f172a", color: "white", borderColor: "#0f172a" },
  h1: { fontSize: "1.6rem", margin: 0 },
  h2: { fontSize: "1.05rem", marginBottom: 4 },
  subnote: { fontSize: "0.78rem", color: "#9ca3af", marginBottom: 16 },
  select: { padding: "8px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: "0.9rem" },
  kpiRow: { display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 24 },
  kpiCard: { border: "1px solid #e5e7eb", borderRadius: 10, padding: "16px 18px", backgroundColor: "white", minWidth: 160 },
  kpiLabel: { fontSize: "0.78rem", color: "#6b7280", fontWeight: 500 },
  kpiValue: { fontSize: "1.5rem", fontWeight: 700, marginTop: 4 },
  section: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 20, marginBottom: 20 },
  chartGrid: { display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 },
  chartCard: {},
  chartTitle: { fontSize: "0.85rem", fontWeight: 600, color: "#374151", marginBottom: 4 },
};