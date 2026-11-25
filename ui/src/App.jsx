import { useState } from "react";
import { MotionConfig } from "framer-motion";
import { AudioLines } from "lucide-react";

import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Settings from "./pages/Settings";
import Tutorial from "./pages/Tutorial";

import Navbar from "./components/Navbar";
import { MODE_LABELS } from "./components/ui";
import { useSettings } from "./contexts/SettingsContext";

function RunStatus() {
  const { dashboardState } = useSettings();
  const { isActive, mode } = dashboardState;
  return (
    <div className="flex items-center justify-end gap-2 text-caption" role="status" aria-live="polite">
      <span className="relative flex size-2">
        {isActive && (
          <span className="absolute inline-flex size-full rounded-full bg-success opacity-60 motion-safe:animate-ping" />
        )}
        <span className={`relative inline-flex size-2 rounded-full ${isActive ? "bg-success" : "bg-muted-soft"}`} />
      </span>
      <span className={isActive ? "text-ink font-medium" : "text-muted"}>
        {isActive ? "Running" : "Stopped"}
      </span>
      {isActive && <span className="text-muted">· {MODE_LABELS[mode] || mode}</span>}
    </div>
  );
}

const App = () => {
  const [page, setPage] = useState("dashboard");

  const renderPage = () => {
    switch (page) {
      case "history":
        return <History />;
      case "settings":
        return <Settings />;
      case "tutorial":
        return <Tutorial />;
      default:
        return <Dashboard onNavigate={setPage} />;
    }
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex h-screen flex-col overflow-hidden bg-canvas text-ink">
        <header className="grid h-14 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-4 border-b border-hairline px-6">
          <div className="flex items-center gap-2.5">
            <span className="grid size-6 place-items-center rounded-sm bg-primary text-on-primary" aria-hidden="true">
              <AudioLines className="size-3.5" strokeWidth={2.25} />
            </span>
            <span className="text-title font-medium tracking-[-0.01em] text-ink">MHCI Assistant</span>
          </div>

          <Navbar page={page} setPage={setPage} />

          <RunStatus />
        </header>

        <main className="min-h-0 flex-1">{renderPage()}</main>
      </div>
    </MotionConfig>
  );
};

export default App;
