import React from "react";
import { LayoutDashboard, History as HistoryIcon, Settings as SettingsIcon, CircleHelp } from "lucide-react";

const PAGES = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "history", label: "History", icon: HistoryIcon },
  { id: "settings", label: "Settings", icon: SettingsIcon },
  { id: "tutorial", label: "Help", icon: CircleHelp },
];

const Navbar = ({ page, setPage }) => {
  return (
    <nav aria-label="Main" className="flex items-center gap-1">
      {PAGES.map(({ id, label, icon: Icon }) => {
        const active = page === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => setPage(id)}
            aria-current={active ? "page" : undefined}
            className={`inline-flex h-8 items-center gap-2 rounded-full px-3.5 text-ui font-medium transition-colors duration-150 ${
              active
                ? "bg-card text-ink ring-1 ring-hairline-strong dark:bg-strong dark:ring-0"
                : "text-body hover:bg-strong/60 hover:text-ink"
            }`}
          >
            <Icon className={`size-4 ${active ? "text-ink" : "text-muted"}`} aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </nav>
  );
};

export default Navbar;
