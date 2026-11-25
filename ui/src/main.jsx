import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import { SettingsProvider } from "./contexts/SettingsContext";
import { LogsProvider } from "./contexts/LogsContext";

createRoot(document.getElementById("root")).render(

    <SettingsProvider>
      <LogsProvider>
        <App />
      </LogsProvider>
    </SettingsProvider>
  
);
