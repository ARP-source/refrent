"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import BrowserChrome, { type ChromeHandle, type Panels } from "@/components/BrowserChrome";
import BrowserViewport from "@/components/BrowserViewport";
import AnswerPanel from "@/components/CommandBar";
import DreamBackground from "@/components/DreamBackground";
import ObsidianPane from "@/components/ObsidianPane";
import { useRecall } from "@/lib/useRecall";
import { desktop } from "@/lib/desktop";
import RestoreBanner, { HistoricalSnapshot } from "@/components/RestoreBanner";
import AmbiguityDialog from "@/components/AmbiguityDialog";
import TelemPanel from "@/components/TelemPanel";
import { X } from "lucide-react";

const PIN_KEY = "referent.pinChrome";

export default function Home() {
  const s = useRecall();
  const chrome = useRef<ChromeHandle>(null);
  const [electron, setElectron] = useState(false);
  const [panels, setPanels] = useState<Panels>({ recall: false, vault: false });
  const [dismissedChoice, setDismissedChoice] = useState<string | null>(null);
  const [choiceReady, setChoiceReady] = useState(false);
  const choreography = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---- auto-hiding top chrome: visible while hovered, focused, pinned, or briefly after a shortcut
  const [pinned, setPinned] = useState(false);
  const [hover, setHover] = useState(false);
  const [omniFocused, setOmniFocused] = useState(false);
  const [peek, setPeek] = useState(true);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const peekTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chromeVisible = pinned || hover || omniFocused || peek;
  useEffect(() => {
    try { setPinned(localStorage.getItem(PIN_KEY) === "1"); } catch { /* storage unavailable */ }
    peekTimer.current = setTimeout(() => setPeek(false), 3500);
    return () => { if (peekTimer.current) clearTimeout(peekTimer.current); };
  }, []);
  const togglePin = () => setPinned((p) => {
    try { localStorage.setItem(PIN_KEY, p ? "0" : "1"); } catch { /* storage unavailable */ }
    return !p;
  });
  const enterChrome = () => { if (hideTimer.current) clearTimeout(hideTimer.current); setHover(true); };
  const leaveChrome = () => { if (hideTimer.current) clearTimeout(hideTimer.current); hideTimer.current = setTimeout(() => setHover(false), 700); };
  const reveal = useCallback((ms = 2500) => {
    setPeek(true);
    if (peekTimer.current) clearTimeout(peekTimer.current);
    peekTimer.current = setTimeout(() => setPeek(false), ms);
  }, []);
  const focusOmnibox = useCallback((recall = false) => { reveal(); chrome.current?.focusOmnibox(recall); }, [reveal]);

  // Desktop app: the main process reports the cursor's y (the native page view hides it from the DOM).
  const chromeBox = useRef<HTMLDivElement>(null);
  const hoverRef = useRef(false);
  hoverRef.current = hover;
  useEffect(() => desktop()?.onEvent((msg) => {
    if (msg.type !== "pointer" || typeof msg.y !== "number") return;
    if (msg.y >= 0 && msg.y <= 10) {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      setHover(true);
      return;
    }
    const bottom = chromeBox.current?.getBoundingClientRect().bottom ?? 0;
    if (hoverRef.current && (msg.y < 0 || msg.y > bottom + 16)) {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(() => setHover(false), 600);
    } else if (hoverRef.current && hideTimer.current) clearTimeout(hideTimer.current);
  }), []);

  const toggle = useCallback((p: keyof Panels) => {
    if (choreography.current) clearTimeout(choreography.current);
    setPanels((v) => ({ recall: p === "recall" && !v.recall, vault: p === "vault" && !v.vault }));
  }, []);
  const closePanels = () => { if (choreography.current) clearTimeout(choreography.current); setPanels({ recall: false, vault: false }); };
  const showChoice = !!s.ambiguity && choiceReady && dismissedChoice !== s.ambiguity.rid;

  useEffect(() => {
    if (!s.graphRun) return;
    setChoiceReady(false);
    setPanels({ vault: true, recall: false });
    choreography.current = setTimeout(() => { setPanels({ vault: false, recall: false }); setChoiceReady(true); }, 2500);
    return () => { if (choreography.current) clearTimeout(choreography.current); };
  }, [s.graphRun]);

  useEffect(() => {
    desktop()?.overlay("dialog", showChoice || s.snapshotOpen);
    return () => desktop()?.overlay("dialog", false);
  }, [showChoice, s.snapshotOpen]);

  useEffect(() => desktop()?.onEvent((msg) => {
    if (msg.type !== "shortcut") return;
    if (msg.key === "l" || msg.key === "k") focusOmnibox(msg.key === "k");
    if (msg.key === "j") toggle("recall");
    if (msg.key === "b") toggle("vault");
  }), [focusOmnibox, toggle]);

  useEffect(() => {
    if (!showChoice && !s.snapshotOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { s.setSnapshotOpen(false); setDismissedChoice(s.ambiguity?.rid || null); }
      if (e.key !== "Tab") return;
      const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button:not(:disabled)'));
      const first = buttons[0], last = buttons.at(-1);
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showChoice, s.snapshotOpen, s.ambiguity, s.setSnapshotOpen]);

  useEffect(() => setElectron(navigator.userAgent.includes("Electron")), []);

  // browser-style shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      const k = e.key.toLowerCase();
      const active = s.tabs.find((t) => t.active);
      if (k === "l" || k === "k") { e.preventDefault(); focusOmnibox(k === "k"); }
      else if (k === "t") { e.preventDefault(); s.newTab(); setTimeout(() => focusOmnibox(), 300); }
      else if (k === "w" && active) { e.preventDefault(); s.closeTab(active.id); }
      else if (k === "j") { e.preventDefault(); toggle("recall"); }
      else if (k === "b") { e.preventDefault(); toggle("vault"); }
      else if (k === "r") { e.preventDefault(); s.send({ type: "input", kind: "reload" }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s, focusOmnibox, toggle]);

  const dock = panels.recall || panels.vault;

  return (
    <main className="relative flex h-screen flex-col overflow-hidden">
      <DreamBackground />
      <div ref={chromeBox} onMouseEnter={enterChrome} onMouseLeave={leaveChrome} className="relative z-30 shrink-0">
        <div className="chrome-wrap" data-hidden={!chromeVisible} data-instant={electron}>
          <div>
            <BrowserChrome ref={chrome} s={s} panels={panels} toggle={toggle} closePanels={closePanels} electron={electron}
              pinned={pinned} onPin={togglePin} onFocusChange={setOmniFocused}
              onRecall={() => { setChoiceReady(false); setPanels({ vault: true, recall: false }); }} />
          </div>
        </div>
        {!chromeVisible && <button aria-label="Show toolbar" title="Show toolbar (Ctrl+L)" onClick={() => reveal(4000)} className="group block h-3 w-full"><span className="reveal-strip block group-hover:opacity-100" /></button>}
      </div>
      {s.error && <div role="alert" className="glass mx-2 mt-2 flex items-center gap-3 rounded-xl px-4 py-2 text-sm text-rose-700"><span className="flex-1">{s.error}</span><button onClick={() => s.setError(null)} aria-label="Dismiss error"><X size={16} /></button></div>}
      {s.captureMessage && <div role="status" className="glass mx-2 mt-2 flex items-center gap-3 rounded-xl px-4 py-2 text-sm text-emerald-800"><span className="flex-1">{s.captureMessage}</span><button onClick={() => { setPanels({ vault: true, recall: false }); s.setCaptureMessage(null); }} className="font-medium text-orange-600 underline">Show in vault</button><button onClick={() => s.setCaptureMessage(null)} aria-label="Dismiss capture confirmation"><X size={16} /></button></div>}

      <div className="flex min-h-0 flex-1 gap-2 p-2">
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[18px] shadow-[0_24px_60px_-28px_rgba(6,48,84,.55),0_0_0_1px_rgba(255,255,255,.7)]">
          <RestoreBanner s={s} />
          <TelemPanel s={s} />
          <div className="min-h-0 flex-1">
            <BrowserViewport s={s} />
          </div>
        </div>
        {dock && (
          <aside className={`dock-in flex shrink-0 flex-col gap-2 ${panels.vault ? "w-[46%]" : "w-[420px]"}`}>
            <div className="flex items-center justify-between px-3 pt-1 text-xs font-semibold text-sky-900"><span>{panels.vault ? "Episodic vault graph" : "Search intelligence & baseline"}</span><button aria-label="Close panel" className="rounded-lg p-1 hover:bg-white/70" onClick={closePanels}><X size={15} /></button></div>
            {panels.recall && (
              <div className="flex min-h-0 flex-1 flex-col">
                <AnswerPanel s={s} />
              </div>
            )}
            {panels.vault && (
              <div className="flex min-h-0 flex-1 flex-col">
                <ObsidianPane s={s} />
              </div>
            )}
          </aside>
        )}
      </div>
      {showChoice && <AmbiguityDialog s={s} onClose={() => { setDismissedChoice(s.ambiguity!.rid); setPanels({ vault: false, recall: true }); }} />}
      <HistoricalSnapshot s={s} />
    </main>
  );
}
