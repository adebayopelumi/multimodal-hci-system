import React, { createContext, useContext, useEffect, useState } from "react";

const SETTINGS_KEY = "capstone-settings";

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [theme, setTheme] = useState("dark");
  const [autoStart, setAutoStart] = useState(false);
  // Which inputs "Start assistant on launch" starts: "both" | "voice" | "gesture"
  const [startMode, setStartMode] = useState("both");
  const [microphone, setMicrophone] = useState("default");
  const [webcam, setWebcam] = useState("default");
  const [gestureEnabled, setGestureEnabled] = useState(true);
  const [recordAudio, setRecordAudio] = useState(false);
  const [saveSnapshots, setSaveSnapshots] = useState(false);

  // 🔹 NEW: dashboard UI state that should survive page switches
  const [dashboardState, setDashboardState] = useState({
    isActive: false,
    isMicActive: true,
    isCameraActive: true,
    mode: "both",
  });

  // Load from storage
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (!raw) return;

      const s = JSON.parse(raw);

      if (s.theme) setTheme(s.theme);
      if (typeof s.autoStart === "boolean") setAutoStart(s.autoStart);
      if (["both", "voice", "gesture"].includes(s.startMode)) setStartMode(s.startMode);
      if (s.microphone) setMicrophone(s.microphone);
      if (s.webcam) setWebcam(s.webcam);
      if (typeof s.gestureEnabled === "boolean")
        setGestureEnabled(s.gestureEnabled);
      if (typeof s.recordAudio === "boolean") setRecordAudio(s.recordAudio);
      if (typeof s.saveSnapshots === "boolean")
        setSaveSnapshots(s.saveSnapshots);
      // dashboardState is NOT loaded from storage on purpose –
      // we just want it to persist while the app is open, not across reloads
    } catch (err) {
      console.error("settings load error", err);
    }
  }, []);

  // Save to storage (only persistent settings, not dashboardState)
  useEffect(() => {
    const settings = {
      theme,
      autoStart,
      startMode,
      microphone,
      webcam,
      gestureEnabled,
      recordAudio,
      saveSnapshots,
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [
    theme,
    autoStart,
    startMode,
    microphone,
    webcam,
    gestureEnabled,
    recordAudio,
    saveSnapshots,
  ]);

  // Apply theme
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [theme]);

  return (
    <SettingsContext.Provider
      value={{
        theme,
        setTheme,
        autoStart,
        setAutoStart,
        startMode,
        setStartMode,
        microphone,
        setMicrophone,
        webcam,
        setWebcam,
        gestureEnabled,
        setGestureEnabled,
        recordAudio,
        setRecordAudio,
        saveSnapshots,
        setSaveSnapshots,

        // 🔹 NEW: shared dashboard state
        dashboardState,
        setDashboardState,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettings must be used within SettingsProvider");
  }
  return ctx;
}
