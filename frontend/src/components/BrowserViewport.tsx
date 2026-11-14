"use client";

import { ArrowLeft, ArrowRight, Bot, Camera, FileDiff, Globe, Lock, RotateCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { RecallState } from "@/lib/useRecall";
import { API, VIEW_H, VIEW_W } from "@/lib/types";

export default function BrowserViewport({ s }: { s: RecallState }) {
  const box = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [ping, setPing] = useState(0);
  const [agentVisible, setAgentVisible] = useState(false);
  const down = useRef(false);
  const lastMove = useRef(0);

  const agentActive = s.agent && s.agent.phase !== "done";
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

  const toView = (e: { clientX: number; clientY: number }) => {
    const r = box.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * VIEW_W, y: ((e.clientY - r.top) / r.height) * VIEW_H };
  };

  // wheel needs a non-passive native listener so the outer page does not scroll
  const send = s.send;
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const scale = VIEW_W / r.width;
      send({ type: "input", kind: "wheel", x: ((e.clientX - r.left) / r.width) * VIEW_W, y: ((e.clientY - r.top) / r.height) * VIEW_H, dx: e.deltaX * scale, dy: e.deltaY * scale });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [send]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    if (e.key.length === 1) s.send({ type: "input", kind: "type", text: e.key });
    else s.send({ type: "input", kind: "key", key: e.key });
  };

  const go = (u: string) => s.send({ type: "navigate", url: u.startsWith("/") ? API + u : u });
  const displayUrl = editing ? draft : s.url;
  const secure = s.url.startsWith("https://") || s.url.startsWith(API);

  return (
    <section className="panel flex h-full min-h-0 flex-col overflow-hidden">
      {/* chrome */}
      <div className="flex items-center gap-2 px-3 py-2.5">
        <div className="flex gap-0.5 text-slate-400">
          <button className="rounded-full p-1.5 hover:bg-white/5" title="Back" onClick={() => s.send({ type: "input", kind: "back" })}><ArrowLeft size={15} /></button>
          <button className="rounded-full p-1.5 hover:bg-white/5" title="Forward" onClick={() => s.send({ type: "input", kind: "forward" })}><ArrowRight size={15} /></button>
          <button className="rounded-full p-1.5 hover:bg-white/5" title="Reload" onClick={() => s.send({ type: "input", kind: "reload" })}><RotateCw size={15} /></button>
        </div>
        <form
          className="flex flex-1 items-center gap-2 rounded-full bg-black/30 px-3 py-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) go(draft.trim());
            setEditing(false);
            (document.activeElement as HTMLElement | null)?.blur();
          }}
        >
          {secure ? <Lock size={13} className="text-emerald-400" /> : <Globe size={13} className="text-slate-500" />}
          <input
            className="w-full bg-transparent font-mono text-xs text-slate-200 outline-none"
            value={displayUrl}
            spellCheck={false}
            onFocus={() => { setDraft(s.url); setEditing(true); }}
            onBlur={() => setEditing(false)}
            onChange={(e) => setDraft(e.target.value)}
          />
        </form>
        <button
          onClick={() => s.capture()}
          title="Remember this page"
          className="rounded-full p-2 text-cyan-200 transition hover:bg-cyan-400/15"
        >
          <Camera size={16} />
        </button>
      </div>

      {/* viewport */}
      <div className="relative flex min-h-0 flex-1 items-center justify-center px-2 pb-2">
        <div
          ref={box}
          tabIndex={0}
          onKeyDown={onKey}
          onMouseDown={(e) => { down.current = true; box.current?.focus(); s.send({ type: "input", kind: "down", ...toView(e) }); }}
          onMouseUp={(e) => { down.current = false; s.send({ type: "input", kind: "up", ...toView(e) }); }}
          onMouseMove={(e) => {
            const now = performance.now();
            if (now - lastMove.current < (down.current ? 30 : 120)) return;
            lastMove.current = now;
            s.send({ type: "input", kind: "move", ...toView(e) });
          }}
          className={`relative max-h-full w-full cursor-default select-none overflow-hidden rounded-2xl outline-none transition-shadow duration-500 ${agentVisible ? "shadow-[0_0_0_1px_rgba(47,180,245,.55),0_0_50px_rgba(2,151,222,.45)]" : "shadow-[0_20px_50px_-20px_rgba(0,0,0,.8)]"}`}
          style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}`, maxWidth: `calc((100vh - 230px) * ${VIEW_W / VIEW_H})` }}
        >
          {s.frame ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={s.frame} alt="Live browser" draggable={false} className="absolute inset-0 h-full w-full" />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-slate-500">
              <Globe className="animate-pulse" />
              {s.status?.browser.error ? <span className="max-w-md text-center text-rose-400">{s.status.browser.error}</span> : s.connected ? "Waiting for first frame..." : "Connecting to backend..."}
            </div>
          )}

          {/* agent cursor */}
          {agentVisible && s.cursor && (
            <div className="pointer-events-none absolute z-10" style={{ left: `${(s.cursor.x / VIEW_W) * 100}%`, top: `${(s.cursor.y / VIEW_H) * 100}%` }}>
              <span key={ping} className="cursor-ping absolute -left-3 -top-3 h-6 w-6 rounded-full bg-cyan-400/60" />
              <svg width="22" height="22" viewBox="0 0 24 24" className="drop-shadow-[0_2px_8px_rgba(2,151,222,.8)]">
                <path d="M3 2l7.5 19 2.6-7.9L21 10.5z" fill="#5fc4f2" stroke="#02070A" strokeWidth="1.5" strokeLinejoin="round" />
              </svg>
            </div>
          )}

          {/* what changed since you last looked - on the page itself */}
          {s.changes?.status === "changed" && (
            <div className="absolute inset-x-3 bottom-3 z-20 flex flex-wrap items-center gap-2 rounded-2xl bg-[#06121b]/90 px-3.5 py-2.5 shadow-[0_20px_40px_-10px_rgba(0,0,0,.8)] backdrop-blur-xl">
              <FileDiff size={15} className="text-orange-300" />
              <span className="text-[13px] font-medium text-white">
                Changed since you looked{s.changes.edited_by ? <span className="font-normal text-orange-200/80"> - {s.changes.edited_by}</span> : null}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {s.changes.changes?.slice(0, 5).map((c, i) => (
                  <span key={i} className="rounded-lg bg-white/[0.06] px-2 py-0.5 font-mono text-[12px]">
                    <span className="text-rose-300/80 line-through">{c.before || "-"}</span>
                    <span className="mx-1 text-slate-500">-&gt;</span>
                    <span className="text-emerald-300">{c.after || "-"}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {agentVisible && agentActive && (
            <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-full bg-[#06121b]/85 px-3 py-1.5 text-xs text-cyan-100 backdrop-blur-xl">
              <Bot size={13} className="animate-pulse" /> Taking you back...
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
