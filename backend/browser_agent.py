"""Playwright Chromium controller.

* Streams the page through CDP `Page.startScreencast` (JPEG frames -> WebSocket).
* Forwards user mouse / keyboard input from the embedded viewport.
* Records user actions (clicks, text selections, scrolls) for episode capture.
* Inspects the live DOM (entities, page context) for the deictic resolver.
* Replays recorded action sequences with an animated agent cursor and highlights the
  exact element / text fragment (in-page highlight + bounding box sent to the UI).
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from datetime import datetime
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, CDPSession, Page, Playwright, async_playwright

from config import settings
from mock_portals import COOKIE, SESSION_VALUE

Emit = Callable[[dict[str, Any]], Awaitable[None]]
EmitFrame = Callable[[bytes], Awaitable[None]]

START_PATH = "/portals/canvas/courses/cs229/announcements"
ALLOWED_KEYS = re.compile(r"^(?:[A-Za-z0-9]|Enter|Backspace|Tab|Escape|Delete|ArrowUp|ArrowDown|ArrowLeft|ArrowRight|Home|End|PageUp|PageDown|Space|Shift|Control|Alt|Meta|F5|[ -~])$")

RECORDER_JS = r"""
(() => {
  if (window.__recallInstalled) return; window.__recallInstalled = true;
  const cssPath = (el) => {
    if (!(el instanceof Element)) return '';
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      if (el.id) { parts.unshift('#' + CSS.escape(el.id)); break; }
      let sel = el.tagName.toLowerCase();
      const parent = el.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter(c => c.tagName === el.tagName);
        if (sibs.length > 1) sel += `:nth-of-type(${sibs.indexOf(el) + 1})`;
      }
      parts.unshift(sel); el = parent;
    }
    return parts.join(' > ');
  };
  window.__recallCssPath = cssPath;
  const anchorOf = (el) => { const a = el.closest('[id]'); return a ? '#' + CSS.escape(a.id) : cssPath(el); };
  const send = (o) => { try { window.__recallRecord && window.__recallRecord(JSON.stringify(o)); } catch (e) {} };
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[target]'); if (a) a.target = '_self';
    const t = (e.target.closest && e.target.closest('a,button,[id]')) || e.target;
    send({type: 'click', selector: cssPath(t), text: (t.innerText || '').trim().slice(0, 80)});
  }, true);
  document.addEventListener('mouseup', () => {
    const s = window.getSelection(); const t = s ? s.toString().trim() : '';
    if (t.length > 3 && s.anchorNode) {
      const n = s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement;
      send({type: 'select', selector: n ? anchorOf(n) : '', text: t.slice(0, 300)});
    }
  }, true);
  let st; window.addEventListener('scroll', () => { clearTimeout(st); st = setTimeout(() => send({type: 'scroll', y: Math.round(scrollY)}), 450); }, {passive: true});
})();
"""

SNAPSHOT_JS = r"""
() => {
  const vw = innerWidth, vh = innerHeight;
  const byName = new Map();
  for (const el of document.querySelectorAll('[data-entity]')) {
    const r = el.getBoundingClientRect();
    const inView = r.width > 0 && r.bottom > 56 && r.top < vh && r.right > 0 && r.left < vw;
    const dist = Math.round(Math.hypot(r.left + r.width / 2 - vw / 2, r.top + r.height / 2 - vh / 2));
    const e = {name: el.dataset.entity, type: el.dataset.entityType || 'entity', pronouns: el.dataset.pronouns || '',
               role: el.dataset.role || '', inViewport: inView, dist,
               selector: window.__recallCssPath ? window.__recallCssPath(el) : ''};
    const prev = byName.get(e.name);
    if (!prev || (e.inViewport && !prev.inViewport) || (e.inViewport === prev.inViewport && e.dist < prev.dist)) byName.set(e.name, e);
  }
  let ctx = null; try { ctx = JSON.parse(document.body && document.body.dataset.recall || 'null'); } catch (e) {}
  const blocks = [];
  for (const el of document.querySelectorAll('h1,h2,h3,p,li,td,pre')) {
    const r = el.getBoundingClientRect();
    if (r.bottom > 0 && r.top < vh && r.height > 0) blocks.push((el.innerText || '').trim());
    if (blocks.join(' ').length > 1800) break;
  }
  const sel = window.getSelection ? String(window.getSelection()) : '';
  return {url: location.href, title: document.title, context: ctx, entities: [...byName.values()],
          visibleText: blocks.filter(Boolean).join('\n').slice(0, 2000), scrollY: Math.round(scrollY), selection: sel.slice(0, 300)};
}
"""

HIGHLIGHT_JS = r"""
([sel, text, label]) => {
  if (!document.getElementById('__recall_style')) {
    const s = document.createElement('style'); s.id = '__recall_style';
    s.textContent = `@keyframes __recallPulse{0%,100%{box-shadow:0 0 0 4px rgba(2,151,222,.25),0 0 28px rgba(2,151,222,.55)}50%{box-shadow:0 0 0 9px rgba(2,151,222,.12),0 0 46px rgba(2,151,222,.85)}}
      .__recall_hl{position:absolute;border:3px solid #0297DE;border-radius:10px;pointer-events:none;z-index:2147483646;animation:__recallPulse 1.4s ease-in-out infinite;background:rgba(2,151,222,.06)}
      .__recall_tag{position:absolute;pointer-events:none;z-index:2147483647;background:linear-gradient(90deg,#02070A,#0279b3);color:#fff;font:600 12px/1 ui-sans-serif,system-ui;padding:6px 10px;border-radius:999px;box-shadow:0 4px 18px rgba(2,151,222,.45)}
      mark.__recall_mark{background:#ffd9cc;color:inherit;border-radius:3px;box-shadow:0 0 0 3px #FC734D;padding:0 1px}`;
    document.head.appendChild(s);
  }
  document.querySelectorAll('.__recall_hl,.__recall_tag').forEach(n => n.remove());
  document.querySelectorAll('mark.__recall_mark').forEach(m => { const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m); p.removeChild(m); p.normalize(); });
  let el = null; try { el = sel ? document.querySelector(sel) : null; } catch (e) {}
  let mark = null;
  if (text) {
    const scope = el || document.body; const needle = text.toLowerCase();
    const w = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT); let node;
    while ((node = w.nextNode())) {
      const i = node.nodeValue.toLowerCase().indexOf(needle);
      if (i >= 0) {
        const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + text.length);
        mark = document.createElement('mark'); mark.className = '__recall_mark';
        try { r.surroundContents(mark); } catch (e) { mark = null; }
        if (!el) el = node.parentElement;
        break;
      }
    }
  }
  if (!el) return null;
  (mark || el).scrollIntoView({block: 'center', behavior: 'instant'});
  const er = el.getBoundingClientRect();
  const box = document.createElement('div'); box.className = '__recall_hl';
  Object.assign(box.style, {left: (er.left + scrollX - 8) + 'px', top: (er.top + scrollY - 8) + 'px', width: (er.width + 16) + 'px', height: (er.height + 16) + 'px'});
  document.body.appendChild(box);
  const tag = document.createElement('div'); tag.className = '__recall_tag'; tag.textContent = 'RecallOS - ' + label;
  Object.assign(tag.style, {left: (er.left + scrollX - 8) + 'px', top: Math.max(0, er.top + scrollY - 40) + 'px'});
  document.body.appendChild(tag);
  const tr = mark ? mark.getBoundingClientRect() : er;
  const snapEl = el.matches('[data-snapshot]') ? el : (el.querySelector('[data-snapshot]') || el);
  const ed = el.closest('[data-last-edited-by]') || el.querySelector('[data-last-edited-by]');
  return {x: er.left, y: er.top, w: er.width, h: er.height, tx: tr.left, ty: tr.top, tw: tr.width, th: tr.height, textFound: !!mark,
          liveText: (snapEl.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 4000),
          editedBy: ed ? ed.dataset.lastEditedBy : null, editedAt: ed ? ed.dataset.lastEditedAt : null};
}
"""


class BrowserAgent:
    def __init__(self, emit: Emit, emit_frame: EmitFrame):
        self.emit = emit
        self.emit_frame = emit_frame
        self.pw: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.cdp: CDPSession | None = None
        self.ready = False
        self.error: str | None = None
        self.cursor = (settings.viewport_w / 2, settings.viewport_h / 2)
        self.recording = True
        self.session_actions: list[dict[str, Any]] = []
        self.lock = asyncio.Lock()
        self.last_frame: bytes | None = None

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        try:
            self.pw = await async_playwright().start()
            self.browser = await self.pw.chromium.launch(headless=settings.headless)
            self.context = await self.browser.new_context(
                viewport={"width": settings.viewport_w, "height": settings.viewport_h}, device_scale_factor=1
            )
            await self.context.add_cookies([{"name": COOKIE, "value": SESSION_VALUE, "url": settings.base_url}])
            await self.context.add_init_script(RECORDER_JS)
            self.page = await self.context.new_page()
            await self.page.expose_function("__recallRecord", self._on_record)
            self.page.on("framenavigated", self._on_nav)
            self.context.on("page", self._on_popup)
            self.cdp = await self.context.new_cdp_session(self.page)
            self.cdp.on("Page.screencastFrame", self._on_frame)
            await self.cdp.send(
                "Page.startScreencast",
                {"format": "jpeg", "quality": 70, "maxWidth": settings.viewport_w, "maxHeight": settings.viewport_h, "everyNthFrame": 1},
            )
            await self.page.goto(settings.base_url + START_PATH, wait_until="domcontentloaded")
            self.ready = True
            self.error = None
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            print(f"[browser] failed to start: {self.error}")

    async def stop(self) -> None:
        for closer in (
            lambda: self.cdp.send("Page.stopScreencast") if self.cdp else None,
            lambda: self.browser.close() if self.browser else None,
            lambda: self.pw.stop() if self.pw else None,
        ):
            try:
                c = closer()
                if c:
                    await c
            except Exception:
                pass
        self.ready = False

    # ------------------------------------------------------------------ events
    async def _on_frame(self, params: dict[str, Any]) -> None:
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:
            return
        data = base64.b64decode(params["data"])
        self.last_frame = data
        await self.emit_frame(data)

    async def _on_nav(self, frame) -> None:
        if not self.page or frame != self.page.main_frame:
            return
        url = frame.url
        try:
            title = await self.page.title()
        except Exception:
            title = ""
        await self.emit({"type": "url", "url": url, "title": title})
        if self.recording and not self.lock.locked() and url.startswith("http"):
            self._record({"type": "goto", "url": url})

    async def _on_popup(self, popup: Page) -> None:
        """Keep everything in one tab: open popups in the main page instead."""
        try:
            url = popup.url
            await popup.close()
            if url and url.startswith("http") and self.page:
                await self.page.goto(url, wait_until="domcontentloaded")
        except Exception:
            pass

    async def _on_record(self, payload: str) -> None:
        if not self.recording or self.lock.locked():
            return
        try:
            action = json.loads(payload)
        except ValueError:
            return
        self._record(action)

    def _record(self, action: dict[str, Any]) -> None:
        action["at"] = datetime.now().isoformat(timespec="seconds")
        if self.page:
            action.setdefault("page", self.page.url)
        # collapse consecutive scrolls
        if action["type"] == "scroll" and self.session_actions and self.session_actions[-1]["type"] == "scroll":
            self.session_actions[-1] = action
        else:
            self.session_actions.append(action)
        self.session_actions = self.session_actions[-200:]
        asyncio.create_task(self.emit({"type": "recorded", "action": action, "buffer": len(self.session_actions)}))

    # ------------------------------------------------------------------ public
    def status(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "error": self.error,
            "url": self.page.url if self.page and self.ready else None,
            "busy": self.lock.locked(),
            "buffer": len(self.session_actions),
            "viewport": {"w": settings.viewport_w, "h": settings.viewport_h},
        }

    async def snapshot(self) -> dict[str, Any]:
        if not self.ready or not self.page:
            return {"url": None, "title": None, "context": None, "entities": [], "visibleText": ""}
        try:
            return await self.page.evaluate(SNAPSHOT_JS)
        except Exception as exc:
            return {"url": self.page.url, "title": None, "context": None, "entities": [], "visibleText": "", "error": str(exc)}

    def _abs(self, url: str) -> str:
        """Re-home stored local URLs onto the current backend origin."""
        p = urlparse(url)
        if url.startswith("/"):
            return settings.base_url + url
        if p.hostname in {"127.0.0.1", "localhost"} and p.path.startswith("/portals"):
            return settings.base_url + p.path + (f"?{p.query}" if p.query else "") + (f"#{p.fragment}" if p.fragment else "")
        return url

    async def navigate(self, raw: str) -> None:
        if not self.ready or not self.page:
            return
        url = raw.strip()
        if url.startswith("/"):
            url = settings.base_url + url
        elif not re.match(r"^https?://", url, re.I):
            if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) and not re.match(r"^(localhost|127\.0\.0\.1)(:\d+)?", url):
                raise ValueError("only http(s) URLs are allowed")
            url = ("http://" if url.startswith(("localhost", "127.0.0.1")) else "https://") + url
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("only http(s) URLs are allowed")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:
            await self.emit({"type": "browser_error", "message": str(exc)[:200]})

    async def handle_input(self, msg: dict[str, Any]) -> None:
        if not self.ready or not self.page or self.lock.locked():
            return
        kind = msg.get("kind")
        x = max(0.0, min(float(msg.get("x", 0)), settings.viewport_w))
        y = max(0.0, min(float(msg.get("y", 0)), settings.viewport_h))
        m = self.page.mouse
        try:
            if kind == "move":
                await m.move(x, y)
            elif kind == "down":
                await m.move(x, y)
                await m.down()
            elif kind == "up":
                await m.move(x, y)
                await m.up()
            elif kind == "click":
                await m.click(x, y)
            elif kind == "wheel":
                await m.move(x, y)
                await m.wheel(float(msg.get("dx", 0)), max(-2000.0, min(float(msg.get("dy", 0)), 2000.0)))
            elif kind == "key":
                key = str(msg.get("key", ""))
                if ALLOWED_KEYS.match(key):
                    await self.page.keyboard.press(key)
            elif kind == "type":
                await self.page.keyboard.type(str(msg.get("text", ""))[:500])
            elif kind == "back":
                await self.page.go_back(wait_until="domcontentloaded")
            elif kind == "forward":
                await self.page.go_forward(wait_until="domcontentloaded")
            elif kind == "reload":
                await self.page.reload(wait_until="domcontentloaded")
        except Exception as exc:
            await self.emit({"type": "browser_error", "message": str(exc)[:200]})

    # ------------------------------------------------------------------ replay
    async def _move_cursor(self, x: float, y: float, steps: int = 16) -> None:
        x0, y0 = self.cursor
        for i in range(1, steps + 1):
            t = i / steps
            e = t * t * (3 - 2 * t)  # smoothstep
            cx, cy = x0 + (x - x0) * e, y0 + (y - y0) * e
            await self.emit({"type": "cursor", "x": round(cx, 1), "y": round(cy, 1)})
            await self.page.mouse.move(cx, cy)
            await asyncio.sleep(0.02)
        self.cursor = (x, y)

    async def _click(self, selector: str) -> None:
        loc = self.page.locator(selector).first
        await loc.scroll_into_view_if_needed(timeout=4000)
        box = await loc.bounding_box()
        if not box:
            raise RuntimeError(f"element not visible: {selector}")
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await self._move_cursor(x, y)
        await self.emit({"type": "cursor", "x": x, "y": y, "click": True})
        await self.page.mouse.click(x, y)
        await asyncio.sleep(0.35)
        await self.page.wait_for_load_state("domcontentloaded")

    async def _scroll_to(self, selector: str) -> None:
        found = await self.page.evaluate(
            "(s) => { const el = document.querySelector(s); if (!el) return false; el.scrollIntoView({behavior: 'smooth', block: 'center'}); return true; }",
            selector,
        )
        if not found:
            raise RuntimeError(f"selector not found: {selector}")
        await asyncio.sleep(0.9)

    async def _highlight(self, selector: str, text: str | None, label: str) -> dict[str, Any]:
        rect = await self.page.evaluate(HIGHLIGHT_JS, [selector, text or "", label])
        if not rect:
            raise RuntimeError(f"could not locate {selector} / text fragment")
        await self._move_cursor(rect["tx"] + min(rect["tw"], 60), rect["ty"] + rect["th"] / 2)
        await self.emit({"type": "bbox", "label": label, **{k: v for k, v in rect.items() if k != "liveText"}})
        return rect

    async def element_text(self, selector: str | None) -> str | None:
        if not selector or not self.page:
            return None
        try:
            return await self.page.evaluate(
                "(s) => { const el = document.querySelector(s); if (!el) return null;"
                " const t = el.matches('[data-snapshot]') ? el : (el.querySelector('[data-snapshot]') || el);"
                " return (t.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 4000); }",
                selector,
            )
        except Exception:
            return None

    async def replay(self, actions: list[dict[str, Any]], label: str) -> dict[str, Any]:
        if not self.ready or not self.page:
            return {"ok": False, "error": self.error or "browser not ready", "steps": []}
        async with self.lock:
            t0 = time.perf_counter()
            steps: list[dict[str, Any]] = []
            bbox = None
            await self.emit({"type": "agent", "phase": "takeover", "label": label, "total": len(actions)})
            for i, a in enumerate(actions):
                kind = a.get("type")
                await self.emit({"type": "agent", "phase": "step", "index": i, "action": a})
                ts = time.perf_counter()
                try:
                    if kind == "goto":
                        await self.page.goto(self._abs(a["url"]), wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(0.4)
                    elif kind == "click":
                        await self._click(a["selector"])
                    elif kind == "scroll_to":
                        await self._scroll_to(a["selector"])
                    elif kind == "highlight":
                        bbox = await self._highlight(a.get("selector", ""), a.get("text"), label)
                    elif kind == "wait":
                        await asyncio.sleep(min(float(a.get("seconds", 0.5)), 5))
                    else:
                        raise RuntimeError(f"unknown action type {kind}")
                    steps.append({"index": i, "type": kind, "ok": True, "ms": round((time.perf_counter() - ts) * 1000)})
                except Exception as exc:
                    steps.append({"index": i, "type": kind, "ok": False, "error": str(exc)[:200]})
                    await self.emit({"type": "agent", "phase": "step_error", "index": i, "error": str(exc)[:200]})
            ok = all(s["ok"] for s in steps)
            result = {"ok": ok, "steps": steps, "bbox": bbox, "ms": round((time.perf_counter() - t0) * 1000), "url": self.page.url}
            await self.emit({"type": "agent", "phase": "done", **result})
            return result

    # ------------------------------------------------------------------ capture
    def build_episode(self, snap: dict[str, Any], resolve_name: Callable[[str], str | None]) -> tuple[str, dict, str] | None:
        """Turn the recorded action buffer + current DOM into an episode note."""
        if not snap.get("url"):
            return None
        now = datetime.now()
        selects = [a for a in self.session_actions if a["type"] == "select" and a.get("page") == snap["url"]]
        clicks = [a for a in self.session_actions if a["type"] == "click" and a.get("page") == snap["url"]]
        focus = selects[-1] if selects else None
        selector = focus["selector"] if focus else (clicks[-1]["selector"] if clicks else None)
        fragment = focus["text"] if focus else (snap.get("selection") or None)
        actions: list[dict[str, Any]] = [{"type": "goto", "url": snap["url"]}]
        if selector:
            actions.append({"type": "scroll_to", "selector": selector})
            actions.append({"type": "highlight", "selector": selector, "text": fragment or ""})
        in_view = [e for e in snap.get("entities", []) if e.get("inViewport")]
        people = [e["name"] for e in in_view if e.get("type") == "person"]
        ctx = snap.get("context") or {}
        entities = list(dict.fromkeys([e["name"] for e in in_view if e.get("type") != "person"] + ([ctx["name"]] if ctx.get("name") else [])))

        def link(name: str) -> str:
            return f"[[{name}]]" if resolve_name(name) else name

        title = f"Captured: {snap.get('title') or snap['url']}"[:120]
        slug = re.sub(r"[^a-z0-9]+", "-", (snap.get("title") or "page").lower()).strip("-")[:40]
        note_id = f"ep-{now:%Y-%m-%d-%H%M%S}-{slug or 'page'}"
        fm = {
            "type": "episode",
            "title": title,
            "timestamp": now.isoformat(timespec="seconds"),
            "portal": ctx.get("portal", urlparse(snap["url"]).hostname),
            "url": snap["url"],
            "selector": selector,
            "text_fragment": fragment,
            "people": people,
            "entities": entities,
            "session": {"viewport": f"{settings.viewport_w}x{settings.viewport_h}", "scroll_y": snap.get("scrollY", 0),
                        "recorded_actions": len(self.session_actions)},
            "actions": actions,
            "raw_actions": self.session_actions[-30:],
            "generated_by": "browser_capture",
        }
        who = ", ".join(link(p) for p in people) or "nobody in particular"
        what = ", ".join(link(e) for e in entities) or "this page"
        body = f"# {title}\n\nCaptured while browsing {what}. On screen: {who}.\n"
        if fragment:
            body += f"\n> {fragment}\n"
        visible = (snap.get("visibleText") or "").strip()
        if visible:
            body += "\n" + " ".join(visible.split()[:120]) + "\n"
        self.session_actions = []
        return note_id, fm, body
