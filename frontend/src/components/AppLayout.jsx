import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { fetchUploadStatus, resetToDemo } from "../services/api";
import ThemeToggle from "./ThemeToggle";

const navItems = [
  { to: "/", label: "Overview", end: true, icon: "overview" },
  { to: "/analytics", label: "Payments", icon: "payments" },
  { to: "/incidents", label: "Incidents", icon: "incidents" },
  { to: "/upload", label: "Upload data", icon: "upload" },
  { to: "/audit", label: "Audit trail", icon: "audit" },
];

function NavIcon({ name }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };

  const paths = {
    overview: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="4" rx="1.2" /><rect x="13.5" y="10.5" width="7" height="10" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /></>,
    payments: <><path d="M4 7h15M15 3l4 4-4 4" /><path d="M20 17H5m4 4-4-4 4-4" /></>,
    incidents: <><path d="M13 2 4.5 13h6L10 22l9.5-12h-6L13 2Z" /></>,
    upload: <><path d="M12 16V4m-5 5 5-5 5 5" /><path d="M4 16.5v3A1.5 1.5 0 0 0 5.5 21h13a1.5 1.5 0 0 0 1.5-1.5v-3" /></>,
    audit: <><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r=".8" /><circle cx="4" cy="12" r=".8" /><circle cx="4" cy="18" r=".8" /></>,
  };

  return <svg {...common}>{paths[name]}</svg>;
}

export default function AppLayout() {
  const [activeDataset, setActiveDataset] = useState(null);
  const location = useLocation();

  const refreshStatus = () => {
    fetchUploadStatus().then((d) => setActiveDataset(d.active_dataset)).catch(() => {});
  };

  useEffect(() => { refreshStatus(); }, []);

  const handleReset = async () => {
    await resetToDemo();
    refreshStatus();
    window.location.href = "/";
  };

  const currentPage = navItems.find((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
  )?.label || "Workspace";

  return (
    <div className="app-shell">
      <motion.aside
        className="app-sidebar"
        initial={{ opacity: 0, x: -22 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true"><span>M</span></div>
          <div className="brand-copy">
            <span className="brand-name">metriva</span>
            <span className="brand-caption">PAYMENT INTELLIGENCE</span>
          </div>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sidebar-link${isActive ? " is-active" : ""}`}
            >
              {({ isActive }) => (
                <>
                  <span className="sidebar-link-icon"><NavIcon name={item.icon} /></span>
                  <span className="sidebar-link-label">{item.label}</span>
                  {isActive && <motion.span layoutId="active-sidebar-link" className="sidebar-active-pill" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-bottom-card">
          <div className="sidebar-live-indicator"><span /> LIVE DATA PIPELINE</div>
          <p>Payment signals, brought into focus.</p>
          <span className="sidebar-bottom-foot">METRIVA · MERCHANT OPERATIONS</span>
        </div>
        <div className="sidebar-footer">© 2026 Metriva</div>
      </motion.aside>

      <div className="app-workspace">
        <header className="workspace-topbar">
          <div className="topbar-heading">
            <span className="topbar-eyebrow">MERCHANT OPERATIONS</span>
            <span className="topbar-current-page">{currentPage}</span>
          </div>
          <div className="topbar-right">
          <ThemeToggle />
            <div className="topbar-avatar" title="Metriva workspace">M</div>
          </div>
        </header>

        {activeDataset === "uploaded" && (
          <motion.div
            className="dataset-banner"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            <span className="dataset-banner-dot" />
            <span>Viewing your uploaded dataset, not the demo data.</span>
            <button className="reset-link" onClick={handleReset}>Switch back to demo</button>
          </motion.div>
        )}

        <main className="main-content">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              className="route-content"
              initial={{ opacity: 0, y: 12, filter: "blur(3px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -7, filter: "blur(2px)" }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              <Outlet context={{ refreshDatasetStatus: refreshStatus }} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
