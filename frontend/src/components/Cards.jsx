import { motion } from "motion/react";

export function KpiCard({ label, value, sub, tone = "default" }) {
  return (
    <motion.div
      className={`kpi-card kpi-card-${tone}`}
      whileHover={{ y: -4, transition: { duration: 0.18 } }}
      transition={{ type: "spring", stiffness: 340, damping: 26 }}
    >
      <div className="kpi-card-topline">
        <div className="kpi-label">{label}</div>
        <span className="kpi-card-indicator" />
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </motion.div>
  );
}

export function SeverityBadge({ severity }) {
  return <span className={`status-badge severity-${String(severity || "unknown").toLowerCase()}`}>{severity}</span>;
}

export function StatusBadge({ status }) {
  return <span className={`status-badge state-${String(status || "unknown").toLowerCase()}`}>{status}</span>;
}
