// electron/main.js
const { app, BrowserWindow, ipcMain, Menu } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

function getPythonProjectRoot() {
  if (app.isPackaged) {
    try {
      return fs.readFileSync(
        path.join(process.resourcesPath, "project_path.txt"),
        "utf-8"
      ).trim();
    } catch (e) {
      return path.join(process.resourcesPath, "project");
    }
  }
  return path.join(__dirname, "..");
}

Menu.setApplicationMenu(null);

let mainWindow = null;
let pythonProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.on("closed", async () => {
    mainWindow = null;
    try {
      await stopPythonProcess();
    } catch (e) {}
  });

  if (process.env.ELECTRON_START_URL) {
    mainWindow.loadURL(process.env.ELECTRON_START_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../ui/dist/index.html"));
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", async () => {
  try {
    await stopPythonProcess();
  } catch (e) {}

  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", async () => {
  try {
    await stopPythonProcess();
  } catch (e) {}
});

/* -------------------------------------------------
   PYTHON PROCESS CONTROL
------------------------------------------------- */

function getPythonModule(mode) {
  if (mode === "voice") return "engine.voice.voice_main_wake";
  if (mode === "gesture") return "engine.gesture.gesture_runtime";
  return "engine.run_voice_and_gesture"; // both
}

// pick venv python if available
function resolvePythonExe(projectRoot) {
  const isWin = process.platform === "win32";
  const venvPy = isWin
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");

  if (fs.existsSync(venvPy)) return venvPy;

  return isWin ? "python" : "python3";
}

function sendLog(type, message) {
  if (!mainWindow) return;
  mainWindow.webContents.send("assistant:log", {
    type,
    message: String(message ?? ""),
  });
}

function stopPythonProcess() {
  return new Promise((resolve) => {
    if (!pythonProcess) return resolve();

    const proc = pythonProcess;
    pythonProcess = null;

    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      resolve();
    };

    proc.once("exit", (code, signal) => {
      sendLog("system", `Python exited (code=${code}, signal=${signal || "none"})`);
      done();
    });

    try {
      if (process.platform === "win32") {
        // Kill entire process tree on Windows
        spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"]);
      } else {
        // If spawned detached, proc.pid is the group leader -> kill the whole group
        try {
          process.kill(-proc.pid, "SIGTERM");
        } catch {
          // fallback: kill just the process
          proc.kill("SIGTERM");
        }
      }
    } catch (e) {
      sendLog("system", `Failed to terminate python: ${String(e)}`);
      return done();
    }

    // hard-kill fallback
    setTimeout(() => {
      if (finished) return;
      try {
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"]);
        } else {
          try {
            process.kill(-proc.pid, "SIGKILL");
          } catch {
            proc.kill("SIGKILL");
          }
        }
      } catch {}
      done();
    }, 2500);
  });
}

ipcMain.handle("assistant:start", async (_event, mode) => {
  // If something is running, stop it first so switching always works
  if (pythonProcess) {
    await stopPythonProcess();
  }

  const moduleName = getPythonModule(mode);

  // project root = repo root that contains /engine and /.venv
  const PYTHON_PROJECT_ROOT = getPythonProjectRoot();

  if (!fs.existsSync(path.join(PYTHON_PROJECT_ROOT, "engine"))) {
    sendLog(
      "system",
      `[Launcher] Project folder not found: ${PYTHON_PROJECT_ROOT}. ` +
        `If you moved the project, update electron/project_path.txt and rebuild the app.`
    );
    return { running: false, error: "project_not_found" };
  }

  const pythonExe = resolvePythonExe(PYTHON_PROJECT_ROOT);

  sendLog("system", `[Launcher] Starting python (${mode}) using: ${pythonExe}`);
  sendLog("system", `[Launcher] Module: ${moduleName}`);
  sendLog("system", `[Launcher] CWD: ${PYTHON_PROJECT_ROOT}`);

  const isWin = process.platform === "win32";

  pythonProcess = spawn(pythonExe, ["-u", "-m", moduleName], {
    cwd: PYTHON_PROJECT_ROOT,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      HEADLESS: (mode === "gesture" || mode === "both") ? "1" : "0",
    },

    // Important: own process group so we can kill children (voice+gesture) reliably
    detached: !isWin,

    // keep pipes so logs still flow to UI
    stdio: ["pipe", "pipe", "pipe"],
  });

  // forward logs to renderer
  pythonProcess.stdout.on("data", (data) => sendLog("stdout", data.toString()));
  pythonProcess.stderr.on("data", (data) => sendLog("stderr", data.toString()));

  pythonProcess.on("error", (err) => {
    sendLog("system", `Python spawn error: ${String(err)}`);
  });

  pythonProcess.on("exit", (code, signal) => {
    sendLog("system", `Python exited (code=${code}, signal=${signal || "none"})`);
    pythonProcess = null;
  });

  // NOTE: do NOT unref() here; it can cause weird behavior with piping / lifecycle.
  // If you really want unref, do it only when you don’t need stdio pipes.

  return { running: true };
});

ipcMain.handle("assistant:cmd", async (_event, payload) => {
  if (!pythonProcess || !pythonProcess.stdin) {
    return { ok: false, error: "python_not_running" };
  }

  try {
    pythonProcess.stdin.write(JSON.stringify(payload) + "\n");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});

ipcMain.handle("assistant:stop", async () => {
  await stopPythonProcess();
  return { stopped: true };
});

ipcMain.handle("assistant:status", async () => {
  return { running: Boolean(pythonProcess) };
});