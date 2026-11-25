import React, { useState, useEffect, useRef } from "react";
import { Mic, Hand, VideoOff, Play, Square, Activity, ArrowRight } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { useLogs } from "../contexts/LogsContext";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  LogRow,
  Page,
  PageHeader,
  Segmented,
  StatusPill,
  MODE_OPTIONS,
} from "../components/ui";

// "Start assistant on launch": read the saved settings once when the app opens,
// so it only fires at launch (not every time you come back to this page).
const LAUNCH_SETTINGS = (() => {
  try {
    return JSON.parse(localStorage.getItem("capstone-settings") || "{}");
  } catch {
    return {};
  }
})();
let autoStartHandled = false;

const Dashboard = ({ onNavigate }) => {
  const { microphone, webcam, gestureEnabled, dashboardState, setDashboardState } = useSettings();

  // pull individual values from shared state
  const { isActive, isMicActive, isCameraActive, mode } = dashboardState;

  const setIsActive = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      isActive: typeof valueOrFn === "function" ? valueOrFn(prev.isActive) : valueOrFn,
    }));
  };

  const setIsCameraActive = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      isCameraActive: typeof valueOrFn === "function" ? valueOrFn(prev.isCameraActive) : valueOrFn,
    }));
  };

  const setMode = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      mode: typeof valueOrFn === "function" ? valueOrFn(prev.mode) : valueOrFn,
    }));
  };

  const [audioLevel, setAudioLevel] = useState(0);
  const [busy, setBusy] = useState(false);

  const [micStream, setMicStream] = useState(null);
  const [camStream, setCamStream] = useState(null);
  const camStreamRef = useRef(null);

  // video element ref for real camera feed
  const videoRef = useRef(null);

  // Shared, in-memory activity log (starts empty each launch; see LogsContext).
  // LogsContext also records everything Python prints.
  const { logs: activityLog, addLog, clearLogs } = useLogs();

  const voiceLive = isActive && isMicActive && mode !== "gesture";
  const gestureLive = isActive && isCameraActive && gestureEnabled && mode !== "voice";

  // fake audio visualizer (still random for now)
  useEffect(() => {
    if (voiceLive) {
      const interval = setInterval(() => {
        setAudioLevel(Math.random() * 100);
      }, 100);
      return () => clearInterval(interval);
    }
    setAudioLevel(0);
  }, [voiceLive]);

  const stopAssistant = async () => {
    // UI first
    setIsActive(false);
    addLog("SYSTEM", "Assistant stopped", "system_stop");

    try {
      if (!window.api) {
        addLog("SYSTEM", "Electron API missing (window.api)", "ipc_error");
        return;
      }
      await window.api.stopAssistant();
      addLog("SYSTEM", "Python stopped", "python_stop");
    } catch (e) {
      console.error(e);
      addLog("SYSTEM", `Stop error: ${String(e)}`, "python_stop_error");
    }
  };

  const startAssistant = async (startMode) => {
    // If already running, stop first (switch behavior)
    if (isActive) {
      await stopAssistant();
    }

    // UI first
    setMode(startMode);
    setIsActive(true);

    addLog("SYSTEM", `Assistant started (${startMode})`, "system_start");

    try {
      if (!window.api) {
        addLog("SYSTEM", "Electron API missing (window.api)", "ipc_error");
        return;
      }
      await window.api.startAssistant(startMode);
      addLog("SYSTEM", `Python started (${startMode})`, "python_start");
    } catch (e) {
      console.error(e);
      addLog("SYSTEM", `Start error: ${String(e)}`, "python_start_error");
      setIsActive(false);
    }
  };

  // Start / Stop button
  const handlePowerClick = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (isActive) await stopAssistant();
      else await startAssistant(mode);
    } finally {
      setBusy(false);
    }
  };

  // Picking a mode while running restarts in that mode; while stopped it just selects it.
  const handleModeSelect = async (nextMode) => {
    if (nextMode === mode || busy) return;
    if (!isActive) {
      setMode(nextMode);
      return;
    }
    setBusy(true);
    try {
      await startAssistant(nextMode);
    } finally {
      setBusy(false);
    }
  };

  // auto-start from settings (once per launch)
  useEffect(() => {
    if (autoStartHandled) return;
    autoStartHandled = true;
    if (LAUNCH_SETTINGS.autoStart === true && !isActive) {
      addLog("SYSTEM", "Assistant auto-started", "auto_start");
      const launchMode = ["both", "voice", "gesture"].includes(LAUNCH_SETTINGS.startMode)
        ? LAUNCH_SETTINGS.startMode
        : "both";
      startAssistant(launchMode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // MIC STREAM (logic same, just used for visualiser / future)
  useEffect(() => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }

    if (!isActive || !isMicActive || mode === "gesture") {
      if (micStream) {
        micStream.getTracks().forEach((t) => t.stop());
        setMicStream(null);
      }
      return;
    }

    const constraints = {
      audio: microphone && microphone !== "default" ? { deviceId: { exact: microphone } } : true,
      video: false,
    };

    navigator.mediaDevices
      .getUserMedia(constraints)
      .then((stream) => {
        if (micStream) {
          micStream.getTracks().forEach((t) => t.stop());
        }
        setMicStream(stream);
        addLog("SYSTEM", "Microphone stream started", "mic_stream_on");
      })
      .catch((err) => {
        console.error("Mic getUserMedia error", err);
        addLog("SYSTEM", "Microphone error / permission denied", "mic_error");
      });

    return () => {
      if (micStream) {
        micStream.getTracks().forEach((t) => t.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, isMicActive, mode, microphone]);

  // CAMERA STREAM
  useEffect(() => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }

    const cameraShouldBeOn = isActive && isCameraActive && gestureEnabled && mode !== "voice";

    // If we shouldn't be using the camera, make sure to fully stop any existing stream
    if (!cameraShouldBeOn) {
      if (camStreamRef.current) {
        camStreamRef.current.getTracks().forEach((t) => t.stop());
        camStreamRef.current = null;
      }
      if (camStream) {
        setCamStream(null);
      }
      return;
    }

    const constraints = {
      audio: false,
      video: webcam && webcam !== "default" ? { deviceId: { exact: webcam } } : true,
    };

    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia(constraints)
      .then((stream) => {
        if (cancelled) {
          // if the effect was cleaned up before this resolved, immediately stop this stream
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        // stop any previous live stream
        if (camStreamRef.current) {
          camStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        camStreamRef.current = stream;
        setCamStream(stream);
        addLog("SYSTEM", "Camera stream started", "camera_stream_on");
      })
      .catch((err) => {
        console.error("Camera getUserMedia error", err);
        addLog("SYSTEM", "Camera error / permission denied", "camera_error");
      });

    // Cleanup for dependency changes / unmount
    return () => {
      cancelled = true;
      if (camStreamRef.current && !cameraShouldBeOn) {
        // if we are turning camera off, make sure it is stopped
        camStreamRef.current.getTracks().forEach((t) => t.stop());
        camStreamRef.current = null;
      }
    };
    // camStream is not in deps on purpose; we use camStreamRef for latest stream
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, isCameraActive, gestureEnabled, mode, webcam]);

  // attach camStream to <video>
  useEffect(() => {
    if (!videoRef.current) return;

    if (camStream) {
      videoRef.current.srcObject = camStream;
      videoRef.current.play().catch((err) => console.log("video play error", err));
    } else {
      videoRef.current.srcObject = null;
    }
  }, [camStream]);

  // sync camera with gestureEnabled
  useEffect(() => {
    if (!gestureEnabled && isCameraActive) {
      setIsCameraActive(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gestureEnabled, isCameraActive]);

  // Final safety: if Dashboard unmounts for any reason, stop any leftover camera stream
  useEffect(() => {
    return () => {
      if (camStreamRef.current) {
        camStreamRef.current.getTracks().forEach((t) => t.stop());
        camStreamRef.current = null;
      }
    };
  }, []);

  const recentLogs = activityLog.slice(0, 40);

  return (
    <Page className="flex h-full min-h-[680px] flex-col gap-5">
      <PageHeader
        title="Dashboard"
        description={
          isActive
            ? 'Say "Hey Jarvis", wait for the chime, then ask. Gestures work whenever your hand is in view.'
            : "Pick what to use, then start the assistant."
        }
        actions={
          <>
            <Segmented
              label="Input mode"
              options={MODE_OPTIONS}
              value={mode}
              onChange={handleModeSelect}
              disabled={busy}
            />
            {isActive ? (
              <Button variant="secondary" onClick={handlePowerClick} disabled={busy} className="min-w-[104px]">
                <Square className="fill-current" aria-hidden="true" />
                Stop
              </Button>
            ) : (
              <Button variant="primary" onClick={handlePowerClick} disabled={busy} className="min-w-[104px]">
                <Play className="fill-current" aria-hidden="true" />
                Start
              </Button>
            )}
          </>
        }
      />

      {/* Live panels */}
      <div className="grid min-h-[300px] flex-1 grid-cols-1 gap-4 md:grid-cols-2">
        {/* Gesture */}
        <Card className="flex min-h-0 flex-col">
          <CardHeader
            icon={Hand}
            title="Gesture"
            actions={<StatusPill live={gestureLive} liveLabel="Tracking" idleLabel="Off" />}
          />
          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
            <div className="relative grid min-h-[150px] flex-1 place-items-center overflow-hidden rounded-md border border-hairline-soft bg-canvas-soft">
              {isCameraActive && gestureEnabled && camStream ? (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="absolute inset-0 h-full w-full object-cover"
                  // Mirror the preview like a selfie camera, matching the gesture
                  // engine (it flips its frames too), so the image moves with your hand.
                  style={{ transform: "scaleX(-1)" }}
                />
              ) : isActive && mode !== "voice" ? (
                <EmptyState compact icon={VideoOff} title="Waiting for the camera">
                  If this stays, allow camera access in System Settings › Privacy &amp; Security.
                </EmptyState>
              ) : (
                <EmptyState compact icon={VideoOff} title="Camera is off">
                  {mode === "voice"
                    ? "Voice mode doesn't use the camera. Switch to Gesture or Voice + Gesture."
                    : "Start the assistant to see your camera here."}
                </EmptyState>
              )}
            </div>
          </div>
        </Card>

        {/* Voice */}
        <Card className="flex min-h-0 flex-col">
          <CardHeader
            icon={Mic}
            title="Voice"
            actions={<StatusPill live={voiceLive} liveLabel="Listening" idleLabel="Off" />}
          />
          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
            <div
              className="flex min-h-[96px] flex-1 items-center justify-center gap-[3px] overflow-hidden rounded-md border border-hairline-soft bg-canvas-soft px-4"
              aria-hidden="true"
            >
              {Array.from({ length: 56 }).map((_, i) => (
                <div
                  key={i}
                  className={`w-[3px] rounded-full transition-[height] duration-100 ${
                    voiceLive ? "bg-ink/75" : "bg-hairline-strong"
                  }`}
                  style={{
                    height: voiceLive
                      ? `${Math.max(10, audioLevel * Math.abs(Math.sin((i + Date.now() / 100) * 0.5)))}%`
                      : "6%",
                  }}
                />
              ))}
            </div>
          </div>
        </Card>
      </div>

      {/* Activity timeline */}
      <Card className="flex h-[216px] shrink-0 flex-col">
        <CardHeader
          icon={Activity}
          title="Activity"
          meta={
            <span className="text-caption tabular-nums text-muted">
              {activityLog.length} {activityLog.length === 1 ? "event" : "events"}
            </span>
          }
          actions={
            <>
              <Button variant="ghost" size="sm" onClick={clearLogs} disabled={!activityLog.length}>
                Clear
              </Button>
              {onNavigate && (
                <Button variant="ghost" size="sm" onClick={() => onNavigate("history")}>
                  View all
                  <ArrowRight aria-hidden="true" />
                </Button>
              )}
            </>
          }
        />
        <div className="min-h-0 flex-1 overflow-y-auto rounded-b-lg bg-canvas-soft">
          {recentLogs.length === 0 ? (
            <EmptyState title="Nothing yet">
              What the assistant hears, sees and does will show up here.
            </EmptyState>
          ) : (
            <ul>
              {recentLogs.map((log) => (
                <LogRow key={log.id} log={log} compact />
              ))}
            </ul>
          )}
        </div>
      </Card>
    </Page>
  );
};

export default Dashboard;
