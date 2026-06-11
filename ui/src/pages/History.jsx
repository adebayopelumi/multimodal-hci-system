//history.jsx
import React, { useEffect, useState } from "react";
import {
  History as HistoryIcon,
  Filter,
  Search,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";

const LOGS_KEY = "capstone-activity-log";

const History = () => {
  const {
    recordAudio,
    saveSnapshots,
    autoStart,
    clearLogs, // from SettingsContext
  } = useSettings();

  const [logs, setLogs] = useState([]);
  const [filterType, setFilterType] = useState("ALL");
  const [search, setSearch] = useState("");

  // --- load logs from localStorage ---
  const loadLogs = () => {
    try {
      const raw = localStorage.getItem(LOGS_KEY);
      if (!raw) {
        setLogs([]);
        return;
      }
      const parsed = JSON.parse(raw);
      setLogs(Array.isArray(parsed) ? parsed : []);
    } catch (err) {
      console.error("Failed to load logs", err);
      setLogs([]);
    }
  };

  useEffect(() => {
    loadLogs();

    // listen to changes from other tabs/components
    const handleStorage = (e) => {
      if (e.key === LOGS_KEY) {
        loadLogs();
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  // --- filtered logs ---
  const filteredLogs = logs.filter((log) => {
    if (filterType !== "ALL" && log.type !== filterType) return false;
    if (!search.trim()) return true;

    const text = `${log.command || ""} ${log.intent || ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  });

  // --- simple stats ---
  const stats = {
    total: logs.length,
    voice: logs.filter((l) => l.type === "VOICE").length,
    gesture: logs.filter((l) => l.type === "GESTURE").length,
    action: logs.filter((l) => l.type === "ACTION").length,
    system: logs.filter((l) => l.type === "SYSTEM").length,
  };

  const handleClear = () => {
    clearLogs();
    loadLogs();
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#0d0b1e]/60 px-6 py-5 space-y-4">
      {/* HEADER */}
      <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[#1e1b3a] border border-[#3d3870]">
            <HistoryIcon className="w-5 h-5 text-violet-100" />
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-semibold text-white">
              History &amp; Logs
            </h1>
            <p className="text-xs md:text-sm text-violet-300">
              Review past voice commands, gestures and system actions captured
              by the assistant.
            </p>
          </div>
        </div>

        {/* current logging settings snapshot */}
        <div className="flex flex-wrap gap-2 text-[0.65rem] md:text-[0.7rem]">
          <span className="px-2 py-1 rounded-full bg-[#1e1b3a] border border-[#3d3870] text-violet-200">
            Auto-start:{" "}
            <span className={autoStart ? "text-emerald-400" : "text-violet-300"}>
              {autoStart ? "On" : "Off"}
            </span>
          </span>
          <span className="px-2 py-1 rounded-full bg-[#1e1b3a] border border-[#3d3870] text-violet-200">
            Record audio:{" "}
            <span
              className={recordAudio ? "text-emerald-400" : "text-violet-300"}
            >
              {recordAudio ? "On" : "Off"}
            </span>
          </span>
          <span className="px-2 py-1 rounded-full bg-[#1e1b3a] border border-[#3d3870] text-violet-200">
            Save snapshots:{" "}
            <span
              className={saveSnapshots ? "text-emerald-400" : "text-violet-300"}
            >
              {saveSnapshots ? "On" : "Off"}
            </span>
          </span>
        </div>
      </header>

      {/* TOP ROW: STATS + CONTROLS */}
      <div className="grid gap-3 md:grid-cols-[2fr,3fr]">
        {/* Stats cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3">
            <p className="text-[0.7rem] text-violet-300">Total events</p>
            <p className="text-lg font-semibold text-white">
              {stats.total}
            </p>
          </div>
          <div className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3">
            <p className="text-[0.7rem] text-violet-300">Voice</p>
            <p className="text-lg font-semibold text-emerald-400">
              {stats.voice}
            </p>
          </div>
          <div className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3">
            <p className="text-[0.7rem] text-violet-300">Gestures</p>
            <p className="text-lg font-semibold text-sky-400">
              {stats.gesture}
            </p>
          </div>
          <div className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3">
            <p className="text-[0.7rem] text-violet-300">Actions / System</p>
            <p className="text-lg font-semibold text-purple-400">
              {stats.action + stats.system}
            </p>
          </div>
        </div>

        {/* Filters & actions */}
        <div className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <div className="inline-flex items-center gap-2 text-xs text-violet-200">
              <Filter className="w-3.5 h-3.5 text-violet-300" />
              <span>Filter by type</span>
            </div>
            <div className="inline-flex gap-1 rounded-lg bg-[#1e1b3a]/80 p-0.5 text-[0.7rem]">
              {["ALL", "VOICE", "GESTURE", "ACTION", "SYSTEM"].map((t) => (
                <button
                  key={t}
                  onClick={() => setFilterType(t)}
                  className={`px-2 py-0.5 rounded-md ${
                    filterType === t
                      ? "bg-violet-200 text-[#0d0b1e]"
                      : "text-violet-200 hover:bg-[#2e2a5a]/80"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Search + buttons */}
          <div className="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center mt-1">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-white0 absolute left-2 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search command or intent…"
                className="w-full pl-7 pr-3 py-1.5 rounded-md bg-[#0d0b1e]/80 border border-[#3d3870] text-xs text-white placeholder:text-white0 focus:outline-none focus:border-violet-400"
              />
            </div>
            <button
              onClick={loadLogs}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-[#4c4888] bg-[#1e1b3a] px-3 py-1.5 text-[0.7rem] text-white hover:bg-[#2e2a5a]"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
            <button
              onClick={handleClear}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-rose-500 bg-rose-500/10 px-3 py-1.5 text-[0.7rem] text-rose-200 hover:bg-rose-500/20"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* LOG LIST */}
      <section className="flex-1 bg-[#13112b]/80 border border-[#2e2a5a] rounded-lg p-3 flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold flex items-center gap-2 text-violet-100">
            <HistoryIcon className="w-3.5 h-3.5 text-purple-400" />
            Live Activity Log
          </h2>
          <span className="text-[0.65rem] text-white0">
            Showing {filteredLogs.length} of {logs.length} events
          </span>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5">
          {filteredLogs.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-white0">
              No log entries yet. Interact with the assistant on the Dashboard
              to see events here.
            </div>
          ) : (
            filteredLogs.map((log) => (
              <div
                key={log.id}
                className="flex items-center gap-2 bg-[#0d0b1e]/70 px-2 py-1.5 rounded border border-[#2e2a5a] text-xs"
              >
                <span className="text-white0 font-mono min-w-[60px] text-[10px]">
                  {log.timestamp}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-semibold min-w-[60px] text-center ${
                    log.type === "VOICE"
                      ? "bg-emerald-500/15 text-emerald-300"
                      : log.type === "GESTURE"
                      ? "bg-sky-500/15 text-sky-300"
                      : log.type === "ACTION"
                      ? "bg-purple-500/15 text-purple-300"
                      : log.type === "SYSTEM"
                      ? "bg-amber-500/15 text-amber-300"
                      : "bg-slate-500/20 text-violet-200"
                  }`}
                >
                  {log.type}
                </span>
                <span className="text-white flex-1 truncate">
                  {log.command || "—"}
                </span>
                {log.intent && (
                  <span className="text-violet-300 font-mono text-[10px] max-w-[150px] truncate">
                    {log.intent}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};

export default History;
