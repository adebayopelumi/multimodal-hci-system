import React, { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";

export default function Settings() {
  const {
    theme,
    setTheme,
    autoStart,
    setAutoStart,

    startMode,
    setStartMode,

    clearLogs,
  } = useSettings();

  useEffect(() => {
    if (!window.api?.saveSettings) return;

    window.api.saveSettings({
      autoStart,
      startMode,
    });
  }, [autoStart, startMode]);

  useEffect(() => {
    if (!window.api?.setAutoStart) return;
    window.api.setAutoStart(autoStart);
  }, [autoStart]);

  return (
    <div className="h-full w-full overflow-y-auto px-6 py-5 space-y-4 bg-[#0d0b1e]/60">
      <header className="flex flex-col gap-2">
        <h1 className="text-xl md:text-2xl font-semibold text-white flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-violet-300" />
          Settings
        </h1>
      </header>

      {/* GENERAL */}
      <section className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-xl p-4 md:p-5 space-y-3">
        <h2 className="text-sm font-semibold text-white">General</h2>

        <div className="grid gap-4 md:grid-cols-2">
          {/* Auto start */}
          <div>
            <label className="text-xs text-violet-100">Auto-start</label>
            <label className="flex gap-2 items-center mt-1 text-white text-xs">
              <input
                type="checkbox"
                className=" w-5 h-5"
                checked={autoStart}
                onChange={(e) => {
                  const value = e.target.checked;
                  setAutoStart(value);

                  // 🔑 IMMEDIATE persistence
                  const raw = localStorage.getItem("capstone-settings");
                  const prev = raw ? JSON.parse(raw) : {};
                  localStorage.setItem(
                    "capstone-settings",
                    JSON.stringify({ ...prev, autoStart: value }),
                  );
                }}
              />
              Start assistant on launch
            </label>
          </div>
        </div>
      </section>

      {/* ASSISTANT */}
      <section className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-xl p-4 md:p-5 space-y-3">
        <h2 className="text-sm font-semibold text-white">Assistant</h2>

        {/* Start mode */}
        <div>
          <label className="text-xs text-violet-100">Auto-start mode</label>
          <select
            className="w-full mt-1 rounded-md border border-[#3d3870] bg-[#0d0b1e]/70 px-2 py-1 text-xs"
            value={startMode}
            onChange={(e) => setStartMode(e.target.value)}
            disabled={!autoStart}
          >
            <option value="voice">Voice only</option>
            <option value="gesture">Gesture only</option>
            <option value="both">Voice + Gesture</option>
          </select>
          {!autoStart && (
            <p className="text-[10px] text-white0 mt-1">
              Enable auto-start to use this option
            </p>
          )}
        </div>
      </section>

      {/* LOGS */}
      <section className="bg-[#13112b]/80 border border-[#2e2a5a] rounded-xl p-4 md:p-5 mb-6">
        <h2 className="text-sm font-semibold text-white">Logs</h2>

        <button
          onClick={clearLogs}
          className="mt-2 px-3 py-1 border border-red-500 text-red-300 rounded-md text-xs"
        >
          Clear activity logs
        </button>
      </section>
    </div>
  );
}
