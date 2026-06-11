import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Power,
  PowerOff,
  Activity,
  Eye,
  Volume2,
} from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";

const LOGS_KEY = "capstone-activity-log";

const Dashboard = () => {
    const {
    microphone,
    webcam,
    autoStart,
    gestureEnabled,
    recordAudio,
    dashboardState,
    setDashboardState,
  } = useSettings();

  // pull individual values from shared state
  const { isActive, isMicActive, isCameraActive, mode } = dashboardState;

  // helper to update dashboardState in context
  const updateDashboardState = (patch) => {
    setDashboardState((prev) => ({
      ...prev,
      ...patch,
    }));
  };

  // re-create the "setters" so the rest of your code works the same
  const setIsActive = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      isActive:
        typeof valueOrFn === "function"
          ? valueOrFn(prev.isActive)
          : valueOrFn,
    }));
  };

  const setIsMicActive = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      isMicActive:
        typeof valueOrFn === "function"
          ? valueOrFn(prev.isMicActive)
          : valueOrFn,
      
    }));
  };

  const setIsCameraActive = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      isCameraActive:
        typeof valueOrFn === "function"
          ? valueOrFn(prev.isCameraActive)
          : valueOrFn,
    }));
  };

  const setMode = (valueOrFn) => {
    setDashboardState((prev) => ({
      ...prev,
      mode:
        typeof valueOrFn === "function"
          ? valueOrFn(prev.mode)
          : valueOrFn,
    }));
  };

  const [currentGesture, setCurrentGesture] = useState({
    label: "None",
    confidence: 0,
  });
  const [lastVoiceCommand, setLastVoiceCommand] = useState({
    text: "",
    intent: "",
    confidence: 0,
  });
  const [audioLevel, setAudioLevel] = useState(0);

  const [micStream, setMicStream] = useState(null);
  const [camStream, setCamStream] = useState(null);
  const camStreamRef = useRef(null);

  // video element ref for real camera feed
  const videoRef = useRef(null);

  const [activityLog, setActivityLog] = useState(() => {
    try {
      const raw = localStorage.getItem(LOGS_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.error("log parse error", e);
    }
    return [
      {
        id: 1,
        type: "VOICE",
        command: "open chrome",
        intent: "open_chrome",
        timestamp: "10:23:45",
      },
      {
        id: 2,
        type: "GESTURE",
        command: "swipe_left",
        intent: "go_back",
        timestamp: "10:23:47",
      },
      {
        id: 3,
        type: "ACTION",
        command: "Execution success",
        intent: "",
        timestamp: "10:23:48",
      },
    ];
  });

  // persist logs
  useEffect(() => {
    try {
      localStorage.setItem(LOGS_KEY, JSON.stringify(activityLog));
    } catch (e) {
      console.error("log persist error", e);
    }
  }, [activityLog]);

  const addLog = (type, command, intent) => {
    const newLog = {
      id: Date.now(),
      type,
      command,
      intent,
      timestamp: new Date().toLocaleTimeString(),
    };
    setActivityLog((prev) => [newLog, ...prev].slice(0, 50));
  };

  // ✅ Receive logs from Python via Electron and push into UI log panel
useEffect(() => {
  if (!window.api || !window.api.onLog) return;

  const unsubscribe = window.api.onLog((data) => {
    const msg = String(data?.message || "").trim();
    if (!msg) return;

    addLog(
      data.type === "stderr" ? "SYSTEM" : "ACTION",
      msg,
      data.type || ""
    );

    // If later you print JSON from python, this will auto-update panels
    try {
      const obj = JSON.parse(msg);

      if (obj.type === "GESTURE") {
        setCurrentGesture({
          label: obj.label || "Unknown",
          confidence: Number(obj.confidence || 0),
        });
        addLog("GESTURE", obj.label || "gesture", obj.intent || "");
      }

      if (obj.type === "VOICE") {
        setLastVoiceCommand({
          text: obj.text || "",
          intent: obj.intent || "",
          confidence: Number(obj.confidence || 0),
        });
        addLog("VOICE", obj.text || "voice", obj.intent || "");
      }
    } catch {}
  });

  return () => unsubscribe && unsubscribe();
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);

  // auto-start from settings
  useEffect(() => {
    if (autoStart && !isActive) {
      setIsActive(true);
      addLog("SYSTEM", "Assistant auto-started", "auto_start");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  // fake audio visualizer (still random for now)
  useEffect(() => {
    if (isActive && isMicActive && mode !== "gesture") {
      const interval = setInterval(() => {
        setAudioLevel(Math.random() * 100);
      }, 100);
      return () => clearInterval(interval);
    } else {
      setAudioLevel(0);
    }
  }, [isActive, isMicActive, mode]);

  const toggleAssistant = async () => {
  const next = !isActive;
  setIsActive(next);

  addLog(
    "SYSTEM",
    next ? "Assistant started" : "Assistant stopped",
    next ? "system_start" : "system_stop"
  );

  try {
    if (!window.api) {
      addLog("SYSTEM", "Electron API missing (window.api)", "ipc_error");
      return;
    }

    if (next) {
      await window.api.startAssistant(mode);
      addLog("SYSTEM", `Python started (${mode})`, "python_start");

      // ✅ sync python with current toggles immediately
      if (window.api.sendCommand) {
        await window.api.sendCommand({ cmd: "mic", on: isMicActive });
        await window.api.sendCommand({ cmd: "camera", on: isCameraActive });
        await window.api.sendCommand({ cmd: "set_mode", mode });
      }
    } else {
      

      await window.api.stopAssistant();
      addLog("SYSTEM", "Python stopped", "python_stop");
    }
  } catch (e) {
    console.error(e);
    addLog("SYSTEM", `Python control error: ${String(e)}`, "python_error");
  }
};

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

// optional helper if you want ONE stop button always visible
const handleStopClick = async () => {
  if (!isActive) return;
  await stopAssistant();
};

  const handleModeChange = async (nextMode) => {
  setMode(nextMode);
  addLog("SYSTEM", `Mode changed to ${nextMode}`, `mode_${nextMode}`);

  // ✅ Tell Python (don’t restart, just switch mode)
  try {
    if (isActive && window.api?.sendCommand) {
      addLog("SYSTEM", `Sent to python: mode=${nextMode}`, "ipc_mode");
    }
  } catch (e) {
    addLog("SYSTEM", `IPC mode error: ${String(e)}`, "ipc_error");
  }
};

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
      audio:
        microphone && microphone !== "default"
          ? { deviceId: { exact: microphone } }
          : true,
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

  const cameraShouldBeOn =
    isActive && isCameraActive && gestureEnabled && mode !== "voice";

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
    video:
      webcam && webcam !== "default"
        ? { deviceId: { exact: webcam } }
        : true,
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
}, [isActive, isCameraActive, gestureEnabled, mode, webcam]);


  // attach camStream to <video>
  useEffect(() => {
    if (!videoRef.current) return;

    if (camStream) {
      videoRef.current.srcObject = camStream;
      videoRef.current
        .play()
        .catch((err) => console.log("video play error", err));
    } else {
      videoRef.current.srcObject = null;
    }
  }, [camStream]);

  // sync camera with gestureEnabled
  useEffect(() => {
    if (!gestureEnabled && isCameraActive) {
      setIsCameraActive(false);
    }
  }, [gestureEnabled, isCameraActive]);

  const toggleMic = async () => {
  const next = !isMicActive;

  setIsMicActive(next);

  addLog(
    "SYSTEM",
    next ? "Microphone unmuted" : "Microphone muted",
    next ? "mic_on" : "mic_off"
  );

  // ✅ Tell Python
  try {
    if (window.api?.sendCommand) {
      await window.api.sendCommand({ cmd: "mic", on: next });
      addLog("SYSTEM", `Sent to python: mic=${next}`, "ipc_mic");
    }
  } catch (e) {
    addLog("SYSTEM", `IPC mic error: ${String(e)}`, "ipc_error");
  }
};

  const toggleCamera = async () => {
  const next = !isCameraActive;

  setIsCameraActive(next);

  addLog(
    "SYSTEM",
    next ? "Camera enabled" : "Camera disabled",
    next ? "camera_on" : "camera_off"
  );

  // ✅ Tell Python
  try {
    if (window.api?.sendCommand) {
      await window.api.sendCommand({ cmd: "camera", on: next });
      addLog("SYSTEM", `Sent to python: camera=${next}`, "ipc_camera");
    }
  } catch (e) {
    addLog("SYSTEM", `IPC camera error: ${String(e)}`, "ipc_error");
  }
};

  // Final safety: if Dashboard unmounts for any reason, stop any leftover camera stream
useEffect(() => {
  return () => {
    if (camStreamRef.current) {
      camStreamRef.current.getTracks().forEach((t) => t.stop());
      camStreamRef.current = null;
    }
  };
}, []);


  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Control Bar */}
      {/* Control Bar */}
<div className="flex items-center justify-between px-4 py-2 bg-[#1e1b3a] border-b border-[#3d3870]">
  <div className="flex items-center gap-2">
    <button
      onClick={() => startAssistant("both")}
      className="px-4 py-2 rounded-lg font-semibold bg-violet-600 hover:bg-violet-700 transition-all"
    >
      Start Both
    </button>

    <button
      onClick={() => startAssistant("voice")}
      className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-700 transition-all"
    >
      Start Voice
    </button>

    <button
      onClick={() => startAssistant("gesture")}
      className="px-4 py-2 rounded-lg font-semibold bg-sky-600 hover:bg-sky-700 transition-all"
    >
      Start Gesture
    </button>

    <button
      onClick={handleStopClick}
      disabled={!isActive}
      className={`px-4 py-2 rounded-lg font-semibold transition-all ${
        isActive
          ? "bg-red-600 hover:bg-red-700"
          : "bg-[#3d3870] cursor-not-allowed opacity-60"
      }`}
    >
      Stop
    </button>
  </div>

  <div className="text-xs text-violet-200">
    Status:{" "}
    <span className={isActive ? "text-green-400" : "text-red-400"}>
      {isActive ? `Running (${mode})` : "Stopped"}
    </span>
  </div>
</div>

      {/* Main Content */}
      <div className="flex-1 flex gap-3 p-3 overflow-hidden">
        {/* Webcam / Gesture Panel */}
        <div className="flex-1 bg-[#1e1b3a] rounded-lg p-3 border border-[#3d3870] flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Video className="w-4 h-4 text-violet-400" />
              Gesture Detection
            </h2>
            <div
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                isCameraActive && gestureEnabled && isActive && mode !== "voice"
                  ? "bg-green-500/20 text-green-400"
                  : "bg-red-500/20 text-red-400"
              }`}
            >
              {isCameraActive && gestureEnabled && isActive && mode !== "voice"
                ? "Active"
                : "Inactive"}
            </div>
          </div>

          {/* REAL VIDEO FEED */}
          <div className="flex-1 bg-[#13112b] rounded-lg mb-2 flex items-center justify-center border border-[#3d3870] min-h-0 overflow-hidden">
            {isCameraActive && gestureEnabled && camStream ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center">
                <VideoOff className="w-10 h-10 text-violet-400/50 mx-auto mb-1" />
                <p className="text-white0 text-xs">
                  Camera disabled or not started
                </p>
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between items-center text-xs">
              <span className="text-violet-300">Gesture:</span>
              <span className="font-semibold text-violet-400">
                {currentGesture.label}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-violet-300">Confidence:</span>
              <span className="font-mono text-green-400">
                {(currentGesture.confidence * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-[#2e2a5a] rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-linear-to-r from-violet-500 to-purple-400 h-full transition-all duration-300"
                style={{ width: `${currentGesture.confidence * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Audio / Voice Panel (still random visualiser) */}
        <div className="flex-1 bg-[#1e1b3a] rounded-lg p-3 border border-[#3d3870] flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Mic className="w-4 h-4 text-green-400" />
              Voice Recognition
            </h2>
            <div
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                isMicActive && isActive && mode !== "gesture"
                  ? "bg-green-500/20 text-green-400"
                  : "bg-red-500/20 text-red-400"
              }`}
            >
              {isMicActive && isActive && mode !== "gesture"
                ? "Listening"
                : "Muted"}
            </div>
          </div>

          <div className="flex-1 bg-[#13112b] rounded-lg p-2 mb-2 border border-[#3d3870] min-h-0">
            <div className="flex items-end justify-center gap-0.5 h-full ">
              {Array.from({ length: 70 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-linear-to-t from-violet-500 to-violet-400 w-1 rounded-full transition-all duration-100"
                  style={{
                    height:
                      isMicActive && isActive && mode !== "gesture"
                        ? `${Math.max(
                            15,
                            audioLevel *
                              Math.abs(
                                Math.sin((i + Date.now() / 100) * 0.5)
                              )
                          )}%`
                        : "10%",
                  }}
                />
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <div>
              <span className="text-violet-300 text-xs">Last Command:</span>
              <p className="font-medium text-sm text-white mt-0.5 truncate">
                {lastVoiceCommand.text || "Waiting for input..."}
              </p>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-violet-300">Intent:</span>
              <span className="font-mono text-purple-400">
                {lastVoiceCommand.intent || "N/A"}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-violet-300">Confidence:</span>
              <span className="font-mono text-green-400">
                {lastVoiceCommand.confidence
                  ? `${(lastVoiceCommand.confidence * 100).toFixed(1)}%`
                  : "0%"}
              </span>
            </div>
            <p className="text-[0.65rem] text-white0">
              Mic device: {microphone || "default"}{" "}
              {recordAudio ? "(recording enabled)" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* Activity Log */}
      <div
        className="bg-[#1e1b3a] mx-3 mb-3 rounded-lg p-2 border border-[#3d3870]"
        style={{ height: "180px" }}
      >
        <h2 className="text-xs font-semibold mb-1.5 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-purple-400" />
          Live Activity Log
        </h2>
        <div
          className="space-y-1 overflow-y-auto"
          style={{ height: "145px" }}
        >
          {activityLog.map((log) => (
            <div
              key={log.id}
              className="flex items-center gap-2 bg-[#13112b] px-2 py-1 rounded border border-[#3d3870] text-xs"
            >
              <span className="text-white0 font-mono min-w-[55px] text-[10px]">
                {log.timestamp}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-semibold min-w-[60px] text-center ${
                  log.type === "VOICE"
                    ? "bg-green-500/20 text-green-400"
                    : log.type === "GESTURE"
                    ? "bg-violet-500/20 text-violet-400"
                    : log.type === "ACTION"
                    ? "bg-purple-500/20 text-purple-400"
                    : log.type === "SYSTEM"
                    ? "bg-amber-500/20 text-amber-300"
                    : "bg-slate-500/20 text-violet-300"
                }`}
              >
                {log.type}
              </span>
              <span className="text-white flex-1 truncate">{log.command}</span>
              {log.intent && (
                <>
                  <span className="text-white0">→</span>
                  <span className="text-violet-300 font-mono text-[10px]">
                    {log.intent}
                  </span>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
 