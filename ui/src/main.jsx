import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import { SettingsProvider } from "./contexts/SettingsContext";
import { LogsProvider } from "./contexts/LogsContext";

// Apply the saved theme before the first paint (dark unless Light was chosen),
// so the window doesn't flash the other theme on launch.
try {
  const saved = JSON.parse(localStorage.getItem("capstone-settings") || "{}");
  document.documentElement.classList.toggle("dark", saved.theme !== "light");
} catch {
  document.documentElement.classList.add("dark");
}

createRoot(document.getElementById("root")).render(

    <SettingsProvider>
      <LogsProvider>
        <App />
      </LogsProvider>
    </SettingsProvider>
  
);
