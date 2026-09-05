import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/incidents", label: "Incidents" },
];

export default function AppLayout() {
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
      <main style={styles.main}>
        <Outlet />
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
  main: { padding: "28px 32px", maxWidth: 1200, margin: "0 auto" },
};
