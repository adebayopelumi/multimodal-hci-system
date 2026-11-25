import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

// Activity logs live in memory only: every launch starts with an empty log,
// and "Clear" empties it everywhere (Dashboard and History share this list).
// Older versions saved logs to localStorage under this key; it's removed on start.
const OLD_LOGS_KEY = "capstone-activity-log";
const MAX_LOGS = 200;

const LogsContext = createContext(null);

// {"type": "VOICE" | "GESTURE", ...} lines printed by the Python engine
export function parseEvent(line) {
  if (!line.startsWith("{")) return null;
  try {
    const obj = JSON.parse(line);
    return obj && typeof obj === "object" ? obj : null;
  } catch {
    return null;
  }
}

export function LogsProvider({ children }) {
  const [logs, setLogs] = useState([]);
  const nextId = useRef(0);

  const addLog = useCallback((type, command, intent = "") => {
    nextId.current += 1;
    const entry = {
      id: `${Date.now()}-${nextId.current}`,
      type,
      command,
      intent,
      timestamp: new Date().toLocaleTimeString(),
    };
    setLogs((prev) => [entry, ...prev].slice(0, MAX_LOGS));
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  // Delete logs saved on disk by older versions.
  useEffect(() => {
    try {
      localStorage.removeItem(OLD_LOGS_KEY);
    } catch {
      // storage unavailable: nothing to clean up
    }
  }, []);

  // Collect output from the Python engine here (always mounted), so nothing
  // is missed while you're on another page.
  useEffect(() => {
    if (!window.api || !window.api.onLog) return;

    const unsubscribe = window.api.onLog((data) => {
      // One chunk of output can hold several printed lines: log each on its own.
      const lines = String(data?.message || "").split(/\r?\n/);
      for (const raw of lines) {
        const line = raw.trim();
        if (!line) continue;

        // Structured events printed by Python as JSON: log them as Voice / Gesture
        const event = parseEvent(line);
        if (event?.type === "GESTURE") {
          addLog("GESTURE", event.label || "gesture", event.intent || "");
          continue;
        }
        if (event?.type === "VOICE") {
          addLog("VOICE", event.text || "voice", event.intent || "");
          continue;
        }

        addLog(data.type === "stdout" ? "ACTION" : "SYSTEM", line, data.type === "stderr" ? "stderr" : "");
      }
    });

    return () => unsubscribe && unsubscribe();
  }, [addLog]);

  return (
    <LogsContext.Provider value={{ logs, addLog, clearLogs }}>
      {children}
    </LogsContext.Provider>
  );
}

export function useLogs() {
  const ctx = useContext(LogsContext);
  if (!ctx) {
    throw new Error("useLogs must be used within LogsProvider");
  }
  return ctx;
}
