export function KpiCard({ label, value, sub, tone = "default" }) {
  return (
    <div style={{ ...styles.card, ...toneStyles[tone] }}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={styles.kpiValue}>{value}</div>
      {sub && <div style={styles.kpiSub}>{sub}</div>}
    </div>
  );
}

export function SeverityBadge({ severity }) {
  return <span style={{ ...styles.badge, ...severityStyles[severity] || {} }}>{severity}</span>;
}

export function StatusBadge({ status }) {
  return <span style={{ ...styles.badge, ...statusStyles[status] || {} }}>{status}</span>;
}

const toneStyles = {
  default: {},
  danger: { borderColor: "#fecaca", backgroundColor: "#fef2f2" },
  warning: { borderColor: "#fde68a", backgroundColor: "#fffbeb" },
};

const severityStyles = {
  CRITICAL: { backgroundColor: "#fee2e2", color: "#991b1b" },
  HIGH: { backgroundColor: "#ffedd5", color: "#9a3412" },
  MEDIUM: { backgroundColor: "#fef9c3", color: "#854d0e" },
  LOW: { backgroundColor: "#e0f2fe", color: "#075985" },
};

const statusStyles = {
  ACTIVE: { backgroundColor: "#fee2e2", color: "#991b1b" },
  WATCH: { backgroundColor: "#fef9c3", color: "#854d0e" },
  RECOVERING: { backgroundColor: "#dbeafe", color: "#1e40af" },
  RESOLVED: { backgroundColor: "#dcfce7", color: "#166534" },
};

const styles = {
  card: {
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: "16px 18px",
    backgroundColor: "white",
    minWidth: 160,
  },
  kpiLabel: { fontSize: "0.78rem", color: "#6b7280", fontWeight: 500 },
  kpiValue: { fontSize: "1.6rem", fontWeight: 700, marginTop: 4 },
  kpiSub: { fontSize: "0.75rem", color: "#9ca3af", marginTop: 2 },
  badge: {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: 999,
    fontSize: "0.72rem",
    fontWeight: 600,
    backgroundColor: "#f3f4f6",
    color: "#374151",
  },
};
