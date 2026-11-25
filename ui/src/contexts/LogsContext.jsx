import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

// Activity logs live in memory only: every launch starts with an empty log,
// and "Clear" empties it everywhere (Dashboard and History share this list).
// Older versions saved logs to localStorage under this key; it's removed on start.
const OLD_LOGS_KEY = "capstone-activity-log";
const MAX_LOGS = 200;

const LogsContext = createContext(null);

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
      const msg = String(data?.message || "").trim();
      if (!msg) return;

      addLog(data.type === "stderr" ? "SYSTEM" : "ACTION", msg, data.type || "");

      // Structured events printed by Python as JSON
      try {
        const obj = JSON.parse(msg);
        if (obj.type === "GESTURE") addLog("GESTURE", obj.label || "gesture", obj.intent || "");
        if (obj.type === "VOICE") addLog("VOICE", obj.text || "voice", obj.intent || "");
      } catch {
        // plain text line
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
