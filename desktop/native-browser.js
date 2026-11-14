const { WebContentsView, ipcMain, Menu, clipboard, screen } = require("electron");

// Pages render as native Chromium surfaces. The shell preload is never exposed to web pages.
module.exports = function installNativeBrowser(win, { base, token, cdp }) {
  const views = new Map();
  const overlays = new Set();
  let active = null;
  let bounds = { x: 8, y: 128, width: 1200, height: 650 };
  let queue = Promise.resolve();
  let closing = false;
  const notify = (msg) => { if (!win.isDestroyed()) win.webContents.send("referent:event", msg); };
  const trusted = (event) => event.sender === win.webContents && event.senderFrame === win.webContents.mainFrame;
  const api = async (route, body) => {
    const response = await fetch(base + route, {
      method: "POST", headers: { "content-type": "application/json", "x-referent-key": token },
      body: JSON.stringify(body), signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) throw new Error((await response.text()).slice(0, 300));
    return response.json();
  };
  const layout = () => {
    const [w, h] = win.getContentSize();
    const x = Math.max(0, Math.min(bounds.x, w));
    const y = Math.max(0, Math.min(bounds.y, h));
    for (const [id, view] of views) {
      view.setBounds({ x, y, width: Math.max(1, Math.min(bounds.width, w - x)), height: Math.max(1, Math.min(bounds.height, h - y)) });
      view.setVisible(id === active && overlays.size === 0 && bounds.width > 0 && bounds.height > 0);
    }
  };
  const normalize = (raw) => {
    let url = String(raw || base + "/portals/canvas/").trim();
    if (url.startsWith("/")) url = base + url;
    if (!/^https?:\/\//i.test(url)) {
      if (/^[a-z][a-z0-9+.-]*:/i.test(url) && !/^(localhost|127\.0\.0\.1):\d+/i.test(url)) throw new Error("Only http and https addresses are supported.");
      url = (/^(localhost|127\.0\.0\.1)(:|\/|$)/.test(url) ? "http://" : "https://") + url;
    }
    if (!["http:", "https:"].includes(new URL(url).protocol)) throw new Error("Unsupported address.");
    return url;
  };
  const activate = async (id) => {
    if (!views.has(id)) return;
    await api("/api/browser/native/select", { id });
    active = id;
    layout();
  };
  const create = async (url) => {
    const view = new WebContentsView({ webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false, backgroundThrottling: false, partition: "persist:referent-browsing" } });
    const wc = view.webContents;
    const id = wc.id;
    views.set(id, view);
    win.contentView.addChildView(view);
    view.setBounds(bounds);
    view.setVisible(false);
    wc.setWindowOpenHandler(({ url }) => { enqueue(() => create(url)); return { action: "deny" }; });
    wc.on("will-navigate", (event, url) => { if (!/^https?:\/\//i.test(url)) event.preventDefault(); });
    wc.on("will-redirect", (event, url) => { if (!/^https?:\/\//i.test(url)) event.preventDefault(); });
    wc.on("did-fail-load", (_e, code, description, url, isMainFrame) => {
      if (isMainFrame && code !== -3) notify({ type: "browser_error", message: `Could not open ${url}: ${description}. Check the address or try again.` });
    });
    wc.on("before-input-event", (event, input) => {
      if (input.type !== "keyDown" || !(input.control || input.meta)) return;
      const key = input.key.toLowerCase();
      if (["l", "k", "t", "w", "j", "b"].includes(key)) {
        event.preventDefault();
        if (key === "t") enqueue(() => create());
        else if (key === "w") enqueue(() => close(id));
        else { win.webContents.focus(); notify({ type: "shortcut", key }); }
      }
    });
    wc.on("context-menu", (_event, params) => {
      const template = [];
      if (params.linkURL && /^https?:/.test(params.linkURL)) template.push({ label: "Open link in new tab", click: () => enqueue(() => create(params.linkURL)) }, { label: "Copy link address", click: () => clipboard.writeText(params.linkURL) }, { type: "separator" });
      template.push({ role: "copy", enabled: !!params.selectionText }, { role: "paste", enabled: params.isEditable }, { role: "selectAll" });
      Menu.buildFromTemplate(template).popup({ window: win });
    });
    const marker = `about:blank#referent-${id}`;
    try {
      await wc.session.cookies.set({ url: base, name: "recall_session", value: "demo-student", httpOnly: true, sameSite: "lax" });
      await wc.loadURL(marker);
      await api("/api/browser/native/attach", { id, marker, endpoint: cdp });
      active = id;
      layout();
      wc.loadURL(normalize(url)).catch((error) => { if (error.code !== "ERR_ABORTED") notify({ type: "browser_error", message: error.message }); });
    } catch (error) {
      notify({ type: "browser_error", message: error.message });
      if (active !== id) { win.contentView.removeChildView(view); wc.close(); views.delete(id); }
    }
  };
  const close = async (id) => {
    const view = views.get(id);
    if (!view) return;
    views.delete(id);
    win.contentView.removeChildView(view);
    view.webContents.close();
    if (active === id) {
      active = null;
      if (views.size) await activate([...views.keys()].at(-1));
      else if (!closing) await create();
    }
    layout();
  };
  function enqueue(fn) {
    queue = queue.then(fn).catch((error) => notify({ type: "browser_error", message: error.message }));
    return queue;
  }
  ipcMain.handle("referent:command", (event, msg) => {
    if (!trusted(event) || !msg || typeof msg !== "object") return;
    return enqueue(async () => {
      const wc = views.get(active)?.webContents;
      if (msg.type === "sync") { if (active) await activate(active); notify({ type: "window", maximized: win.isMaximized() }); }
      else if (msg.type === "navigate" && wc) wc.loadURL(normalize(msg.url)).catch((error) => { if (error.code !== "ERR_ABORTED") notify({ type: "browser_error", message: error.message }); });
      else if (msg.type === "tab") {
        if (msg.action === "new") await create(msg.url);
        if (msg.action === "switch") await activate(msg.id);
        if (msg.action === "close") await close(msg.id);
      } else if (msg.type === "input" && wc) {
        if (msg.kind === "back" && wc.navigationHistory.canGoBack()) wc.navigationHistory.goBack();
        if (msg.kind === "forward" && wc.navigationHistory.canGoForward()) wc.navigationHistory.goForward();
        if (msg.kind === "reload") wc.reload();
      }
    });
  });
  ipcMain.on("referent:bounds", (event, rect) => {
    if (!trusted(event) || !rect || ![rect.x, rect.y, rect.width, rect.height].every(Number.isFinite)) return;
    bounds = Object.fromEntries(Object.entries(rect).filter(([k]) => ["x", "y", "width", "height"].includes(k)).map(([k, v]) => [k, Math.round(v)]));
    layout();
  });
  ipcMain.on("referent:overlay", (event, msg) => {
    if (!trusted(event) || !msg || typeof msg.key !== "string") return;
    if (msg.visible) overlays.add(msg.key); else overlays.delete(msg.key);
    layout();
  });
  ipcMain.on("referent:window", (event, action) => {
    if (!trusted(event)) return;
    if (action === "minimize") win.minimize();
    if (action === "maximize") win.isMaximized() ? win.unmaximize() : win.maximize();
    if (action === "close") win.close();
  });
  // The native page view swallows mouse events and Windows reserves the top pixels of a frameless window
  // for resizing, so the renderer cannot see the cursor reach the top edge. Poll it here instead.
  let lastPointerY = null;
  const pointerTimer = setInterval(() => {
    if (win.isDestroyed() || !win.isVisible() || win.isMinimized()) return;
    const p = screen.getCursorScreenPoint();
    const b = win.getContentBounds();
    const inside = p.x >= b.x && p.x < b.x + b.width && p.y >= b.y - 2 && p.y < b.y + b.height;
    const y = inside ? Math.max(0, p.y - b.y) : -1;
    if (y === lastPointerY) return;
    const near = (v) => v !== null && v >= 0 && v < 320;
    if (near(y) || near(lastPointerY) || (y === -1) !== (lastPointerY === -1)) notify({ type: "pointer", y });
    lastPointerY = y;
  }, 60);
  win.on("closed", () => clearInterval(pointerTimer));
  win.on("resize", layout);
  for (const name of ["maximize", "unmaximize"]) win.on(name, () => notify({ type: "window", maximized: win.isMaximized() }));
  win.on("close", () => {
    closing = true;
    for (const view of views.values()) view.webContents.close();
    views.clear();
  });
  return { start: () => enqueue(() => create()), open: (url) => enqueue(() => create(url)) };
};
