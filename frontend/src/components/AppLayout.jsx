import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { fetchUploadStatus, resetToDemo } from "../services/api";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/analytics", label: "Payments" },
  { to: "/incidents", label: "Incidents" },
  { to: "/upload", label: "Upload Data" },
  { to: "/audit", label: "Audit" },
];

export default function AppLayout() {
  const [activeDataset, setActiveDataset] = useState(null);

  const refreshStatus = () => {
    fetchUploadStatus().then((d) => setActiveDataset(d.active_dataset)).catch(() => {});
  };

  useEffect(() => { refreshStatus(); }, []);

  const handleReset = async () => {
    await resetToDemo();
    refreshStatus();
    window.location.href = "/";
  };

  return (
    <div style={styles.shell}>
      <header style={styles.header}>
        <div style={styles.brand}>
          <span style={styles.brandName}>Metriva</span>
          <span style={styles.brandTag}>Payment Intelligence &amp; Revenue Recovery</span>
        </div>
        <nav style={styles.nav}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
                ...styles.navLink,
                ...(isActive ? styles.navLinkActive : {}),
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {activeDataset === "uploaded" && (
        <div style={styles.datasetBanner}>
          <span>Viewing your uploaded dataset, not the demo data.</span>
          <button style={styles.resetLink} onClick={handleReset}>Switch back to demo</button>
        </div>
      )}

      <main style={styles.main}>
        <Outlet context={{ refreshDatasetStatus: refreshStatus }} />
      </main>
    </div>
  );
}

const styles = {
  shell: {
    minHeight: "100vh",
    fontFamily: "system-ui, -apple-system, sans-serif",
    backgroundColor: "#f9fafb",
    color: "#111827",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 32px",
    backgroundColor: "#0f172a",
    color: "white",
  },
  brand: { display: "flex", flexDirection: "column" },
  brandName: { fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.02em" },
  brandTag: { fontSize: "0.7rem", color: "#94a3b8" },
  nav: { display: "flex", gap: 8 },
  navLink: {
    padding: "6px 14px",
    borderRadius: 6,
    color: "#cbd5e1",
    textDecoration: "none",
    fontSize: "0.9rem",
  },
  navLinkActive: { backgroundColor: "#1e293b", color: "white", fontWeight: 600 },
  datasetBanner: {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 14,
    backgroundColor: "#fef3c7", color: "#92400e", padding: "8px 16px", fontSize: "0.82rem",
  },
  resetLink: {
    background: "none", border: "1px solid #92400e", color: "#92400e", borderRadius: 6,
    padding: "3px 10px", fontSize: "0.78rem", cursor: "pointer", fontWeight: 600,
  },
  main: { padding: "28px 32px", maxWidth: 1200, margin: "0 auto" },
};