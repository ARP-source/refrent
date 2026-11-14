// RecallOS desktop shell (Electron main process).
// Starts the Python backend (FastAPI + Playwright agent + built UI), shows a splash while it boots,
// then opens the app window. Closing the app stops the backend it started.
const { app, BrowserWindow, shell, dialog } = require("electron");
const { spawn, execFile } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const pkg = require("./package.json");
const nativeToken = require("crypto").randomBytes(32).toString("hex");
const debugPort = Number(process.env.RECALL_CDP_PORT || 9338);
app.commandLine.appendSwitch("remote-debugging-port", String(debugPort));
app.commandLine.appendSwitch("remote-debugging-address", "127.0.0.1");
const ROOT = process.env.RECALL_ROOT || (app.isPackaged ? pkg.recallRoot : path.resolve(__dirname, ".."));
let PORT = Number(process.env.RECALL_PORT || 8000);
let BASE = `http://127.0.0.1:${PORT}`;
const SMOKE = process.env.RECALL_SMOKE; // path: capture a screenshot after load, then quit (used for automated checks)
const TEST = process.env.RECALL_TEST === "1";

let backend = null;
let win = null;
let splash = null;
let logStream = null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function get(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode);
    });
    req.on("error", () => resolve(0));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(0);
    });
  });
}

function setStatus(text, isError = false) {
  if (!splash || splash.isDestroyed()) return;
  splash.webContents
    .executeJavaScript(`(() => { const s = document.getElementById('s'); s.textContent = ${JSON.stringify(text)}; s.className = ${JSON.stringify(isError ? "err" : "")}; })()`)
    .catch(() => {});
}

async function ensureBackend() {
  // Each desktop owns its native bridge key. A dev server or older app may already use :8000.
  PORT = await new Promise((resolve, reject) => {
    const server = require("net").createServer();
    server.once("error", () => {
      const fallback = require("net").createServer();
      fallback.once("error", reject);
      fallback.listen(0, "127.0.0.1", () => { const port = fallback.address().port; fallback.close(() => resolve(port)); });
    });
    server.listen(PORT, "127.0.0.1", () => { const port = server.address().port; server.close(() => resolve(port)); });
  });
  BASE = `http://127.0.0.1:${PORT}`;
  const py = path.join(ROOT, "backend", ".venv", "Scripts", "python.exe");
  if (!fs.existsSync(py)) throw new Error(`Python environment not found:\n${py}\n\nRun the one-time setup from the README.`);
  const logFile = path.join(app.getPath("userData"), "backend.log");
  logStream = fs.createWriteStream(logFile, { flags: "a" });
  logStream.write(`\n--- ${new Date().toISOString()} starting backend in ${ROOT}\n`);
  backend = spawn(py, ["main.py"], {
    cwd: path.join(ROOT, "backend"),
    windowsHide: true,
    env: { ...process.env, PYTHONUNBUFFERED: "1", RECALL_PORT: String(PORT), RECALL_NATIVE: "true", RECALL_NATIVE_KEY: nativeToken, RECALL_CDP_PORT: String(debugPort) },
  });
  backend.stdout.pipe(logStream, { end: false });
  backend.stderr.pipe(logStream, { end: false });
  for (let i = 0; i < 160; i++) {
    if (backend.exitCode !== null) throw new Error(`The backend exited during startup (code ${backend.exitCode}).\nLog: ${logFile}`);
    if ((await get(`${BASE}/api/status`)) === 200) return "started";
    await sleep(500);
  }
  throw new Error(`The backend did not start within 80 seconds.\nLog: ${logFile}`);
}

function stopBackend() {
  if (!backend || backend.exitCode !== null) return;
  // kill the whole tree: python + the Playwright Chromium it launched
  if (process.platform === "win32") execFile("taskkill", ["/pid", String(backend.pid), "/T", "/F"], () => {});
  else backend.kill("SIGTERM");
  backend = null;
}

function createSplash() {
  splash = new BrowserWindow({
    width: 560,
    height: 340,
    frame: false,
    resizable: false,
    show: false,
    center: true,
    backgroundColor: "#02070A",
    icon: path.join(__dirname, "icon.png"),
    webPreferences: { contextIsolation: true, sandbox: true },
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
  splash.once("ready-to-show", () => { if (!TEST) splash.show(); });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1680,
    height: 1000,
    minWidth: 1280,
    minHeight: 760,
    show: false,
    title: "Referent",
    backgroundColor: "#02070A",
    icon: path.join(__dirname, "icon.png"),
    titleBarStyle: "hidden",
    frame: false,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false, backgroundThrottling: false, preload: path.join(__dirname, "preload.js") },
  });
  win.setMenuBarVisibility(false);
  const native = require("./native-browser")(win, { base: BASE, token: nativeToken, cdp: `http://127.0.0.1:${debugPort}` });
  native.start();
  // open external links (web results) in the real browser, never inside the app
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) native.open(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith(BASE)) {
      e.preventDefault();
      if (/^https?:\/\//i.test(url)) native.open(url);
    }
  });
  win.loadURL(`${BASE}/`);
  win.once("ready-to-show", () => {
    if (!SMOKE) win.maximize();
    if (!TEST) win.show();
    if (splash && !splash.isDestroyed()) splash.close();
  });
  if (SMOKE) {
    win.webContents.once("did-finish-load", async () => {
      await sleep(9000);
      const img = await win.webContents.capturePage();
      fs.writeFileSync(SMOKE, img.toPNG());
      app.quit();
    });
  }
}

if (!SMOKE && !TEST && !app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(async () => {
    app.setAppUserModelId("dev.recallos.app");
    createSplash();
    try {
      setStatus("Starting the memory engine and browser agent...");
      const how = await ensureBackend();
      setStatus(how === "reused" ? "Connected to running engine" : "Loading your vault...");
      if ((await get(`${BASE}/`)) !== 200) {
        throw new Error("The UI build is missing.\nRun:  cd frontend && npm run build");
      }
      createWindow();
    } catch (err) {
      setStatus(String(err.message || err), true);
      dialog.showErrorBox("Referent could not start", String(err.message || err));
      stopBackend();
      app.quit();
    }
  });

  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", stopBackend);
}
