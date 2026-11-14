"use client";

import { Bot, FileDiff, Globe } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { RecallState } from "@/lib/useRecall";

/**
 * The live page. Fills its container; the remote Chromium viewport is resized to match, so the
 * page renders at the real window size (no letterboxing). Mouse, wheel and keys are forwarded.
 */
export default function BrowserViewport({ s }: { s: RecallState }) {
  const host = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [hostSize, setHostSize] = useState({ w: 0, h: 0 });
  const [ping, setPing] = useState(0);
  const [agentVisible, setAgentVisible] = useState(false);
  const down = useRef(false);
  const lastMove = useRef(0);
  const { w: VW, h: VH } = s.viewport;

  const agentActive = !!s.agent && s.agent.phase !== "done";
  useEffect(() => {
    if (agentActive) setAgentVisible(true);
    else if (agentVisible) {
      const t = setTimeout(() => setAgentVisible(false), 2500);
      return () => clearTimeout(t);
    }
  }, [agentActive, agentVisible]);

  useEffect(() => {
    if (s.cursor?.click) setPing((p) => p + 1);
  }, [s.cursor]);

  // measure the available area and ask the engine to render at exactly that size (debounced)
  const resize = s.resizeViewport;
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(([e]) => {
      const w = Math.floor(e.contentRect.width);
      const h = Math.floor(e.contentRect.height);
      setHostSize({ w, h });
      clearTimeout(t);
      t = setTimeout(() => resize(w, h), 180);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      clearTimeout(t);
    };
  }, [resize, s.connected]);

  // the page box keeps the remote aspect ratio while a resize is in flight
  const aspect = VW / VH;
  const fitW = hostSize.w && hostSize.h ? Math.min(hostSize.w, hostSize.h * aspect) : 0;
  const fitH = fitW / aspect;

  const toView = (e: { clientX: number; clientY: number }) => {
    const r = box.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * VW, y: ((e.clientY - r.top) / r.height) * VH };
  };

  const send = s.send;
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const scale = VW / r.width;
      send({ type: "input", kind: "wheel", x: ((e.clientX - r.left) / r.width) * VW, y: ((e.clientY - r.top) / r.height) * VH, dx: e.deltaX * scale, dy: e.deltaY * scale });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [send, VW, VH]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return; // app shortcuts (Ctrl+L, Ctrl+T ...) stay with the app
    e.preventDefault();
    if (e.key.length === 1) s.send({ type: "input", kind: "type", text: e.key });
    else s.send({ type: "input", kind: "key", key: e.key });
  };

  return (
    <div ref={host} className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-[18px] bg-[#0b141c]">
      <div
        ref={box}
        tabIndex={0}
        onKeyDown={onKey}
        onMouseDown={(e) => { down.current = true; box.current?.focus(); s.send({ type: "input", kind: "down", ...toView(e) }); }}
        onMouseUp={(e) => { down.current = false; s.send({ type: "input", kind: "up", ...toView(e) }); }}
        onMouseMove={(e) => {
          const now = performance.now();
          if (now - lastMove.current < (down.current ? 30 : 100)) return;
          lastMove.current = now;
          s.send({ type: "input", kind: "move", ...toView(e) });
        }}
        className={`relative cursor-default select-none overflow-hidden outline-none transition-shadow duration-500 ${agentVisible ? "shadow-[inset_0_0_0_2px_rgba(95,196,242,.7),0_0_40px_rgba(2,151,222,.4)]" : ""}`}
        style={{ width: fitW || "100%", height: fitH || "100%" }}
      >
        {s.frame ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={s.frame} alt="" draggable={false} className="absolute inset-0 h-full w-full" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-slate-500">
            <Globe className="animate-pulse" />
            {s.status?.browser.error ? <span className="max-w-md text-center text-rose-400">{s.status.browser.error}</span> : s.connected ? "Starting browser..." : "Connecting..."}
          </div>
        )}

        {agentVisible && s.cursor && (
          <div className="pointer-events-none absolute z-10" style={{ left: `${(s.cursor.x / VW) * 100}%`, top: `${(s.cursor.y / VH) * 100}%` }}>
            <span key={ping} className="cursor-ping absolute -left-3 -top-3 h-6 w-6 rounded-full bg-cyan-400/60" />
            <svg width="22" height="22" viewBox="0 0 24 24" className="drop-shadow-[0_2px_8px_rgba(2,151,222,.8)]">
              <path d="M3 2l7.5 19 2.6-7.9L21 10.5z" fill="#5fc4f2" stroke="#02070A" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </div>
        )}

        {s.changes?.status === "changed" && (
          <div className="absolute bottom-4 left-1/2 z-20 flex max-w-[92%] -translate-x-1/2 flex-wrap items-center gap-2 rounded-2xl bg-[#06121b]/92 px-4 py-2.5 shadow-[0_20px_40px_-10px_rgba(0,0,0,.8),0_0_0_1px_rgba(255,255,255,.08)] backdrop-blur-xl">
            <FileDiff size={15} className="text-orange-300" />
            <span className="text-[13px] font-medium text-white">
              Changed since you looked{s.changes.edited_by ? <span className="font-normal text-orange-200/80"> - {s.changes.edited_by}</span> : null}
            </span>
            {s.changes.changes?.slice(0, 5).map((c, i) => (
              <span key={i} className="rounded-lg bg-white/[0.06] px-2 py-0.5 font-mono text-[12px]">
                <span className="text-rose-300/80 line-through">{c.before || "-"}</span>
                <span className="mx-1 text-slate-500">-&gt;</span>
                <span className="text-emerald-300">{c.after || "-"}</span>
              </span>
            ))}
          </div>
        )}

        {agentVisible && agentActive && (
          <div className="pointer-events-none absolute left-1/2 top-3 flex -translate-x-1/2 items-center gap-2 rounded-full bg-[#06121b]/90 px-3.5 py-1.5 text-xs text-cyan-100 shadow-[0_0_0_1px_rgba(95,196,242,.3)] backdrop-blur-xl">
            <Bot size={13} className="animate-pulse" /> Taking you back...
          </div>
        )}
      </div>
    </div>
  );
}
