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

  const [busy, setBusy] = useState(false);

  const [micStream, setMicStream] = useState(null);
  const micStreamRef = useRef(null);
  const barsRef = useRef(null); // the level meter's bars (heights set directly, ~60 times a second)
  const [camStream, setCamStream] = useState(null);
  const camStreamRef = useRef(null);

  // video element ref for real camera feed
  const videoRef = useRef(null);

  // Shared, in-memory activity log (starts empty each launch; see LogsContext).
  // LogsContext also records everything Python prints.
  const { logs: activityLog, addLog, clearLogs } = useLogs();

  const voiceLive = isActive && isMicActive && mode !== "gesture";
  const gestureLive = isActive && isCameraActive && gestureEnabled && mode !== "voice";

  // Live level meter: bars follow what the microphone actually hears.
  // Louder sound = taller bars. Low pitches sit in the middle and higher
  // ones spread outwards, mirrored on both sides.
  useEffect(() => {
    const bars = barsRef.current ? Array.from(barsRef.current.children) : [];
    if (!micStream || !voiceLive || !bars.length) return;

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;

    const ctx = new AudioCtx();
    ctx.resume?.().catch(() => {});
    const source = ctx.createMediaStreamSource(micStream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.72;
    analyser.minDecibels = -85; // quiet room stays near the floor
    analyser.maxDecibels = -25; // normal speech reaches the top
    source.connect(analyser); // analysed only, never played back

    const data = new Uint8Array(analyser.frequencyBinCount);
    const half = Math.floor(bars.length / 2);
    const binHz = ctx.sampleRate / analyser.fftSize;
    // Log-spaced bands across the speech range (90 Hz to 5 kHz)
    const edges = Array.from({ length: half + 1 }, (_, k) =>
      Math.max(1, Math.round((90 * Math.pow(5000 / 90, k / half)) / binHz)),
    );

    let frame;
    const draw = () => {
      analyser.getByteFrequencyData(data);
      for (let k = 0; k < half; k++) {
        let peak = 0;
        for (let j = edges[k]; j < Math.max(edges[k + 1], edges[k] + 1); j++) {
          if (data[j] > peak) peak = data[j];
        }
        // Higher bands carry less energy in speech; lift them a little so the edges move too
        const level = Math.min(1, (peak / 255) * (1 + 0.6 * (k / half)));
        const height = `${Math.max(6, Math.round(level * 100))}%`;
        bars[half - 1 - k].style.height = height;
        bars[half + k].style.height = height;
      }
      frame = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(frame);
      source.disconnect();
      ctx.close().catch(() => {});
      bars.forEach((b) => (b.style.height = "")); // back to the resting height
    };
  }, [micStream, voiceLive]);

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

  // MIC STREAM: open the microphone while voice is on (feeds the level meter)
  useEffect(() => {
    if (!voiceLive || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }

    const constraints = {
      audio: {
        ...(microphone && microphone !== "default" ? { deviceId: { exact: microphone } } : {}),
        // Raw levels, so the meter shows how loud the sound really is
        // (auto gain would make quiet and loud speech look the same)
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      video: false,
    };

    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia(constraints)
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        micStreamRef.current = stream;
        setMicStream(stream);
        addLog("SYSTEM", "Microphone stream started", "mic_stream_on");
      })
      .catch((err) => {
        console.error("Mic getUserMedia error", err);
        addLog("SYSTEM", "Microphone error / permission denied", "mic_error");
      });

    // Turning voice off (or leaving the page) releases the microphone
    return () => {
      cancelled = true;
      if (micStreamRef.current) {
        micStreamRef.current.getTracks().forEach((t) => t.stop());
        micStreamRef.current = null;
      }
      setMicStream(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceLive, microphone]);

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
              ref={barsRef}
              className="flex min-h-[96px] flex-1 items-center justify-center gap-[3px] overflow-hidden rounded-md border border-hairline-soft bg-canvas-soft px-4"
              aria-hidden="true"
            >
              {Array.from({ length: 56 }).map((_, i) => (
                <div
                  key={i}
                  className={`h-[6%] w-[3px] rounded-full ${voiceLive ? "bg-ink/75" : "bg-hairline-strong"}`}
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
