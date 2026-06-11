const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  startAssistant: (mode) => ipcRenderer.invoke("assistant:start", mode),
  stopAssistant: () => ipcRenderer.invoke("assistant:stop"),
  statusAssistant: () => ipcRenderer.invoke("assistant:status"),

  onLog: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("assistant:log", handler);
    return () => ipcRenderer.removeListener("assistant:log", handler);
  },
});