import { useEffect, useState } from "react";
import { motion } from "motion/react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("metriva-theme") || "light"
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("metriva-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((current) =>
      current === "dark" ? "light" : "dark"
    );
  };

  return (
    <motion.button
      className="theme-toggle"
      onClick={toggleTheme}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.94 }}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      aria-pressed={theme === "dark"}
      type="button"
    >
      <motion.span
        key={theme}
        initial={{ rotate: -30, opacity: 0, scale: 0.6 }}
        animate={{ rotate: 0, opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
      >
        {theme === "dark" ? "☀️" : "🌙"}
      </motion.span>

      <span>
        {theme === "dark" ? "Light mode" : "Dark mode"}
      </span>
    </motion.button>
  );
}