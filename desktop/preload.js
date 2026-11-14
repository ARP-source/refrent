const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("referent", {
  command: (message) => ipcRenderer.invoke("referent:command", message),
  bounds: (rect) => ipcRenderer.send("referent:bounds", rect),
  overlay: (key, visible) => ipcRenderer.send("referent:overlay", { key, visible }),
  window: (action) => ipcRenderer.send("referent:window", action),
  onEvent: (callback) => {
    const listener = (_event, message) => callback(message);
    ipcRenderer.on("referent:event", listener);
    return () => ipcRenderer.removeListener("referent:event", listener);
  },
});
