"use client";

import { ArrowLeft, ArrowRight, BarChart3, Camera, Globe, Lock, Maximize2, Minimize2, Minus, Network, Pin, PinOff, Plus, RotateCw, Search, Sparkles, X } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { RecallState } from "@/lib/useRecall";
import { desktop } from "@/lib/desktop";

export type Panels = { recall: boolean; vault: boolean };
export type ChromeHandle = { focusOmnibox: (recall?: boolean) => void };

export const DEMOS = [
  { label: "01 · Find the right guide", query: "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours" },
  { label: "02 · Priya's proposal", query: "the proposal method section we revised with Priya Raman eight days ago" },
  { label: "03 · Too close to guess", query: "the formula sheet I had open last night for Rostova's quiz" },
  { label: "04 · Dana's primer", query: "the Ito calculus primer I read for Dana Chen's MATH 340" },
];

export function looksLikeUrl(raw: string) {
  const s = raw.trim();
  if (!s || /\s/.test(s)) return false;
  return /^(https?:\/\/|localhost(:\d+)?|127\.\d+\.\d+\.\d+|\/)/i.test(s) || /^[\w-]+(\.[\w-]+)+(:\d+)?([/?#]\S*)?$/i.test(s);
}
const iconStyle = "grid h-8 w-8 shrink-0 place-items-center rounded-xl text-sky-900/70 transition hover:bg-white/80 hover:text-sky-950 disabled:opacity-35";
const seg = (on: boolean) => `flex h-8 shrink-0 items-center gap-1.5 rounded-xl px-2.5 text-xs font-medium transition ${on ? "bg-white text-sky-950 shadow-[0_2px_10px_-4px_rgba(2,121,179,.5)]" : "text-sky-900/70 hover:bg-white/60 hover:text-sky-950"}`;

type Props = {
  s: RecallState; panels: Panels; toggle: (p: keyof Panels) => void; closePanels: () => void; onRecall: () => void;
  electron: boolean; pinned: boolean; onPin: () => void; onFocusChange: (focused: boolean) => void;
};

export default forwardRef<ChromeHandle, Props>(
  function BrowserChrome({ s, panels, toggle, closePanels, onRecall, electron, pinned, onPin, onFocusChange }, ref) {
    const input = useRef<HTMLInputElement>(null);
    const [text, setText] = useState("");
    const [focused, setFocused] = useState(false);
    const [mode, setMode] = useState<"web" | "recall">("web");
    const [maximized, setMaximized] = useState(false);
    useEffect(() => { if (!focused && mode === "web") setText(s.url); }, [s.url, focused, mode]);
    useEffect(() => onFocusChange(focused), [focused, onFocusChange]);
    useEffect(() => desktop()?.onEvent((message) => {
      if (message.type === "window") setMaximized(!!message.maximized);
    }), []);
    useImperativeHandle(ref, () => ({ focusOmnibox: (recall = false) => {
      setMode(recall ? "recall" : "web"); setText(recall ? "" : s.url);
      // the chrome may be sliding in; focus once it is laid out
      requestAnimationFrame(() => { input.current?.focus(); input.current?.select(); });
    } }));
    const suggestionOpen = focused && mode === "recall";
    useEffect(() => {
      desktop()?.overlay("omnibox", suggestionOpen);
      return () => desktop()?.overlay("omnibox", false);
    }, [suggestionOpen]);
    const recall = (query: string) => {
      if (s.running) return;
      setText(query); setMode("recall"); setFocused(false); input.current?.blur();
      s.recall(query, { replay: true, enrich: true });
      onRecall();
    };
    const submit = () => {
      const value = text.trim();
      if (!value) return;
      if (looksLikeUrl(value)) s.navigate(value);
      else if (mode === "recall") { recall(value); return; }
      else s.navigate(`https://www.google.com/search?q=${encodeURIComponent(value)}`);
      setMode("web"); setFocused(false); input.current?.blur();
    };
    const ready = s.connected && s.status?.browser.ready;
    return <header className="glass relative z-30 shrink-0 select-none rounded-b-[22px]">
      {/* row 1: brand, tabs, window controls */}
      <div className="app-drag flex h-10 items-end gap-1 pl-3">
        <div className="mb-1.5 mr-3 flex items-baseline gap-2">
          <span className="font-serif text-[22px] leading-none text-sky-950">Referent<span className="text-orange-500">.</span></span>
          <span className="hidden rounded-full bg-sky-100/80 px-2 py-0.5 text-[10px] font-medium text-sky-800 xl:inline">Episodic Disambiguation &amp; Verified Task Resumption</span>
        </div>
        <div className="flex min-w-0 flex-1 items-end gap-1 overflow-hidden">
          {s.tabs.map((tab) => <div key={tab.id} onMouseDown={(e) => { if (e.button === 1) s.closeTab(tab.id); else if (e.button === 0) s.switchTab(tab.id); }} title={tab.title}
            className={`app-nodrag group flex h-8 min-w-[100px] max-w-[220px] flex-1 cursor-default items-center gap-2 rounded-t-xl px-3 text-xs transition ${tab.active ? "bg-white/90 text-sky-950 shadow-[0_-4px_14px_-8px_rgba(2,121,179,.5)]" : "text-sky-900/60 hover:bg-white/50"}`}>
            <Globe size={12} className={`shrink-0 ${tab.active ? "text-orange-500" : ""}`} /><span className="truncate">{tab.title.startsWith("about:blank") ? "New tab" : tab.title || "New tab"}</span>
            <button aria-label={`Close ${tab.title}`} title="Close tab" onMouseDown={(e) => e.stopPropagation()} onClick={() => s.closeTab(tab.id)} className="ml-auto rounded p-1 hover:bg-sky-100"><X size={12} /></button>
          </div>)}
          <button title="New tab (Ctrl+T)" aria-label="New tab" className={`app-nodrag ${iconStyle}`} onClick={() => s.newTab()}><Plus size={16} /></button>
        </div>
        {electron && <div className="app-nodrag ml-2 flex self-stretch">
          <button aria-label="Minimize window" title="Minimize" onClick={() => desktop()?.window("minimize")} className="grid w-11 place-items-center text-sky-900 hover:bg-white/70"><Minus size={15} /></button>
          <button aria-label={maximized ? "Restore window" : "Maximize window"} title={maximized ? "Restore" : "Maximize"} onClick={() => desktop()?.window("maximize")} className="grid w-11 place-items-center text-sky-900 hover:bg-white/70">{maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button>
          <button aria-label="Close application" title="Close" onClick={() => desktop()?.window("close")} className="grid w-11 place-items-center text-sky-900 hover:bg-red-500 hover:text-white"><X size={17} /></button>
        </div>}
      </div>

      {/* row 2: navigation, omnibox, drawer toggles */}
      <div className="flex h-12 items-center gap-1.5 border-t border-white/70 bg-white/45 px-2">
        <button aria-label="Back" title="Back" className={iconStyle} onClick={() => s.send({ type: "input", kind: "back" })}><ArrowLeft size={16} /></button>
        <button aria-label="Forward" title="Forward" className={iconStyle} onClick={() => s.send({ type: "input", kind: "forward" })}><ArrowRight size={16} /></button>
        <button aria-label="Reload" title="Reload" className={iconStyle} onClick={() => s.send({ type: "input", kind: "reload" })}><RotateCw size={15} /></button>
        <div className="flex rounded-full bg-sky-900/[0.07] p-1 text-xs">
          {(["web", "recall"] as const).map((m) => <button key={m} onClick={() => { setMode(m); setText(""); input.current?.focus(); }} className={`rounded-full px-3 py-1 font-medium transition ${mode === m ? (m === "recall" ? "bg-orange-500 text-white shadow-[0_2px_10px_-2px_rgba(252,115,77,.7)]" : "bg-white text-sky-950 shadow-sm") : "text-sky-900/60"}`}>{m === "web" ? "Web" : "Recall"}</button>)}
        </div>
        <form className="glass-input relative mx-1 flex min-w-0 flex-1 items-center gap-2 rounded-full px-3 transition" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          {mode === "recall" ? <Sparkles size={15} className="text-orange-500" /> : s.url.startsWith("https://") ? <Lock size={14} className="text-emerald-600" /> : <Search size={15} className="text-sky-700/60" />}
          <input ref={input} aria-label={mode === "recall" ? "Recall a memory" : "Search the web or enter a URL"} value={text} spellCheck={false}
            placeholder={mode === "recall" ? "Ask the way you remember it…" : "Search the web or enter a URL"}
            onFocus={(e) => { setFocused(true); e.target.select(); }}
            onBlur={() => setFocused(false)} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") input.current?.blur(); }}
            className="h-9 min-w-0 flex-1 bg-transparent text-[13px] text-sky-950 outline-none placeholder:text-sky-900/45" />
          <button type="submit" disabled={mode === "recall" && s.running} className={`rounded-full px-3.5 py-1 text-xs font-semibold transition disabled:opacity-50 ${mode === "recall" ? "bg-gradient-to-b from-orange-400 to-orange-500 text-white shadow-[0_4px_14px_-4px_rgba(252,115,77,.8)]" : "bg-sky-500 text-white"}`}>{s.running && mode === "recall" ? "Recalling…" : mode === "recall" ? "Recall" : "Go"}</button>
          {suggestionOpen && <div className="glass-strong absolute inset-x-0 top-11 rounded-2xl p-2">
            <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sky-800/60">Try a memory</div>
            {DEMOS.map((demo) => <button key={demo.label} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => recall(demo.query)} className="block w-full rounded-xl p-2 text-left text-xs text-sky-950 hover:bg-sky-100/80">{demo.query}</button>)}
          </div>}
        </form>
        <div className="flex items-center gap-0.5 rounded-2xl bg-sky-900/[0.06] p-0.5">
          <button title="Full-screen live browser" aria-pressed={!panels.vault && !panels.recall} onClick={closePanels} className={seg(!panels.vault && !panels.recall)}><Globe size={14} /><span className="hidden lg:inline">Live Browser</span></button>
          <button title="Episodic vault graph (Ctrl+B)" aria-pressed={panels.vault} onClick={() => toggle("vault")} className={seg(panels.vault)}><Network size={14} /><span className="hidden lg:inline">Vault Graph</span></button>
          <button title="Search intelligence & baseline (Ctrl+J)" aria-pressed={panels.recall} onClick={() => toggle("recall")} className={seg(panels.recall)}><BarChart3 size={14} /><span className="hidden lg:inline">Search Intelligence</span></button>
          <button title="Capture current view into the vault" disabled={s.capturing || s.running} onClick={() => s.capture()} className={`${seg(false)} disabled:opacity-40`}><Camera size={14} /><span className="hidden lg:inline">{s.capturing ? "Saving…" : "Capture"}</span></button>
        </div>
        <button title={pinned ? "Unpin toolbar (auto-hide when idle)" : "Pin toolbar open"} aria-label={pinned ? "Unpin toolbar" : "Pin toolbar"} aria-pressed={pinned} onClick={onPin}
          className={`${iconStyle} ${pinned ? "bg-orange-100 text-orange-600 hover:bg-orange-100 hover:text-orange-700" : ""}`}>{pinned ? <Pin size={15} /> : <PinOff size={15} />}</button>
        <span title={ready ? "Browser ready" : "Connecting"} className={`mx-1.5 h-2 w-2 rounded-full ${ready ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,.8)]" : "bg-orange-400"}`} />
      </div>

      {/* row 3: one-click demo memories */}
      <div className="flex h-9 items-center gap-2 overflow-x-auto px-3 text-[11px]">
        <span className="shrink-0 font-semibold uppercase tracking-widest text-sky-800/55">Try a memory</span>
        {DEMOS.map((demo) => <button key={demo.label} title={demo.query} disabled={s.running} onClick={() => recall(demo.query)}
          className="shrink-0 rounded-full bg-white/70 px-3 py-1 font-medium text-sky-900 shadow-[inset_0_0_0_1px_rgba(2,121,179,.15)] transition hover:bg-white hover:text-orange-600 hover:shadow-[inset_0_0_0_1px_rgba(252,115,77,.5)] disabled:opacity-40">{demo.label}</button>)}
        <span className="ml-auto hidden shrink-0 text-sky-800/50 md:inline">Ctrl+L / Ctrl+K to show · move to the top edge to reveal</span>
      </div>
    </header>;
  }
);
