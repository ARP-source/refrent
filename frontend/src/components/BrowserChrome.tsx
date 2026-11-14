"use client";

import {
  ArrowLeft, ArrowRight, AudioLines, BookmarkPlus, Clock3, CornerDownLeft, Globe, Lock, Network, Plus, RotateCw, Search, Sparkles, X,
} from "lucide-react";
import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from "react";
import type { RecallState } from "@/lib/useRecall";

export type Panels = { recall: boolean; vault: boolean };
export type ChromeHandle = { focusOmnibox: () => void };

const SUGGESTIONS = [
  "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours",
  "what is she talking about from 2 weeks ago?",
  "the formula sheet I had open last night for Rostova's quiz",
  "that repo I had open before my Kalman filter broke",
];

/** URL-ish input navigates; anything else is a memory query. */
export function looksLikeUrl(t: string) {
  const s = t.trim();
  if (!s || /\s/.test(s)) return false;
  return /^(https?:\/\/|localhost(:\d+)?|127\.\d+\.\d+\.\d+|\/)/i.test(s) || /^[\w-]+(\.[\w-]+)+(:\d+)?(\/\S*)?$/i.test(s);
}

const pretty = (url: string) => url.replace(/^https?:\/\//, "").replace(/\/$/, "");

function IconButton({ title, onClick, active, children, disabled }: { title: string; onClick: () => void; active?: boolean; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`grid h-8 w-8 place-items-center rounded-full transition disabled:opacity-40 ${active ? "bg-cyan-400/20 text-cyan-100 shadow-[0_0_14px_rgba(2,151,222,.45)]" : "text-slate-300 hover:bg-white/[0.07] hover:text-white"}`}
    >
      {children}
    </button>
  );
}

const BrowserChrome = forwardRef<ChromeHandle, { s: RecallState; panels: Panels; toggle: (p: keyof Panels) => void; onRecall: () => void; electron: boolean }>(
  function BrowserChrome({ s, panels, toggle, onRecall, electron }, ref) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [focused, setFocused] = useState(false);
    const [text, setText] = useState("");
    const [hi, setHi] = useState(-1);

    useImperativeHandle(ref, () => ({
      focusOmnibox: () => {
        inputRef.current?.focus();
        inputRef.current?.select();
      },
    }));

    const typed = focused && text !== s.url;
    const isUrl = looksLikeUrl(text);
    const items = useMemo(() => {
      if (!typed || isUrl) return [];
      const recent = s.history.map((h) => h.query);
      const needle = text.trim().toLowerCase();
      return [...new Set([...recent, ...SUGGESTIONS])]
        .filter((x) => !needle || x.toLowerCase().includes(needle))
        .slice(0, 6)
        .map((x) => ({ text: x, recent: recent.includes(x) }));
    }, [typed, isUrl, text, s.history]);

    const submit = (value = text) => {
      const t = value.trim();
      if (!t) return;
      if (looksLikeUrl(t)) {
        s.navigate(t);
      } else if (!s.running) {
        s.recall(t, { replay: true, enrich: true });
        onRecall();
      }
      setFocused(false);
      setHi(-1);
      inputRef.current?.blur();
    };

    const secure = s.url.startsWith("https://") || /^https?:\/\/(127\.0\.0\.1|localhost)/.test(s.url);
    const leadIcon = typed ? (isUrl ? <Globe size={15} className="text-slate-400" /> : <Sparkles size={15} className="text-[#FC734D]" />) : secure ? <Lock size={14} className="text-emerald-300/80" /> : <Search size={15} className="text-slate-400" />;

    return (
      <header className="relative z-30 shrink-0 select-none">
        {/* tab strip (window drag region in the desktop app) */}
        <div className={`app-drag flex h-10 items-end gap-1 pl-3 ${electron ? "pr-[150px]" : "pr-3"}`}>
          <div className="mb-2 mr-2 flex items-center gap-1.5 text-cyan-100/90">
            <AudioLines size={15} />
          </div>
          <div className="flex min-w-0 flex-1 items-end gap-1 overflow-hidden">
            {s.tabs.map((t) => (
              <div
                key={t.id}
                onMouseDown={(e) => {
                  if (e.button === 1) s.closeTab(t.id); // middle-click closes
                  else s.switchTab(t.id);
                }}
                title={t.title}
                className={`app-nodrag group flex h-8 min-w-[110px] max-w-[230px] flex-1 cursor-default items-center gap-2 rounded-t-xl px-3 text-[12px] transition ${
                  t.active ? "bg-white/[0.09] text-white shadow-[inset_0_1px_0_rgba(255,255,255,.18)]" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <Globe size={12} className={t.active ? "shrink-0 text-cyan-200" : "shrink-0 opacity-60"} />
                <span className="truncate">{t.title || pretty(t.url) || "New tab"}</span>
                <button
                  title="Close tab"
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={() => s.closeTab(t.id)}
                  className={`ml-auto grid h-5 w-5 shrink-0 place-items-center rounded-full hover:bg-white/10 ${t.active ? "opacity-80" : "opacity-0 group-hover:opacity-80"}`}
                >
                  <X size={11} />
                </button>
              </div>
            ))}
            <button title="New tab (Ctrl+T)" onClick={() => s.newTab()} className="app-nodrag mb-1 grid h-7 w-7 shrink-0 place-items-center rounded-full text-slate-400 hover:bg-white/[0.07] hover:text-white">
              <Plus size={15} />
            </button>
          </div>
        </div>

        {/* toolbar */}
        <div className="flex h-12 items-center gap-1.5 bg-white/[0.09] px-2 shadow-[0_1px_0_rgba(255,255,255,.06)] backdrop-blur-xl">
          <IconButton title="Back" onClick={() => s.send({ type: "input", kind: "back" })}><ArrowLeft size={16} /></IconButton>
          <IconButton title="Forward" onClick={() => s.send({ type: "input", kind: "forward" })}><ArrowRight size={16} /></IconButton>
          <IconButton title="Reload" onClick={() => s.send({ type: "input", kind: "reload" })}><RotateCw size={15} /></IconButton>

          {/* omnibox: URLs navigate, everything else recalls a memory */}
          <form
            className="relative mx-1 flex-1"
            onSubmit={(e) => {
              e.preventDefault();
              submit(hi >= 0 && items[hi] ? items[hi].text : text);
            }}
          >
            <div className={`flex h-9 items-center gap-2.5 rounded-full px-4 transition ${focused ? "bg-[#06121b]/95 shadow-[0_0_0_1px_rgba(95,196,242,.45),0_0_24px_rgba(2,151,222,.25)]" : "bg-black/30 hover:bg-black/40"}`}>
              {s.running ? <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-cyan-300/30 border-t-cyan-200" /> : leadIcon}
              <input
                ref={inputRef}
                value={focused ? text : pretty(s.url)}
                spellCheck={false}
                placeholder="Search your memory or enter a URL"
                onFocus={(e) => {
                  setText(s.url);
                  setFocused(true);
                  setHi(-1);
                  requestAnimationFrame(() => e.target.select());
                }}
                onBlur={() => setTimeout(() => setFocused(false), 120)}
                onChange={(e) => {
                  setText(e.target.value);
                  setHi(-1);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") inputRef.current?.blur();
                  if (e.key === "ArrowDown" && items.length) { e.preventDefault(); setHi((h) => (h + 1) % items.length); }
                  if (e.key === "ArrowUp" && items.length) { e.preventDefault(); setHi((h) => (h <= 0 ? items.length - 1 : h - 1)); }
                }}
                className="min-w-0 flex-1 bg-transparent text-[13.5px] text-slate-100 outline-none placeholder:text-slate-500"
              />
              {typed && text.trim() && (
                <span className={`flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${isUrl ? "bg-white/[0.07] text-slate-300" : "bg-[#FC734D]/90 text-white"}`}>
                  {isUrl ? "Go" : "Recall"} <CornerDownLeft size={11} />
                </span>
              )}
            </div>

            {focused && items.length > 0 && (
              <div className="absolute inset-x-0 top-[42px] overflow-hidden rounded-2xl bg-[#06121b]/95 p-1.5 shadow-[0_30px_60px_-20px_rgba(0,0,0,.9),0_0_0_1px_rgba(255,255,255,.06)] backdrop-blur-xl">
                {items.map((it, i) => (
                  <button
                    key={it.text}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => setHi(i)}
                    onClick={() => submit(it.text)}
                    className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-[13px] transition ${i === hi ? "bg-white/[0.07] text-white" : "text-slate-300"}`}
                  >
                    {it.recent ? <Clock3 size={13} className="shrink-0 text-slate-500" /> : <Sparkles size={13} className="shrink-0 text-[#FC734D]/80" />}
                    <span className="truncate">{it.text}</span>
                  </button>
                ))}
              </div>
            )}
          </form>

          <IconButton title="Remember this page" onClick={() => s.capture()}><BookmarkPlus size={16} /></IconButton>
          <div className="mx-1 h-5 w-px bg-white/10" />
          <IconButton title="Recall panel (Ctrl+J)" active={panels.recall} onClick={() => toggle("recall")}>
            <span className="relative">
              <Sparkles size={16} />
              {!panels.recall && (s.result || s.ambiguity) && <span className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-[#FC734D]" />}
            </span>
          </IconButton>
          <IconButton title="Vault (Ctrl+B)" active={panels.vault} onClick={() => toggle("vault")}><Network size={16} /></IconButton>
          <span
            title={s.connected ? (s.status?.browser.ready ? "Online" : "Starting") : "Offline"}
            className={`mx-2 h-1.5 w-1.5 shrink-0 rounded-full ${s.connected && s.status?.browser.ready ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : s.connected ? "bg-amber-400" : "bg-rose-400"}`}
          />
        </div>
      </header>
    );
  },
);

export default BrowserChrome;
