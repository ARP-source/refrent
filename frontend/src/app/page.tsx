"use client";

import { useEffect, useRef, useState } from "react";
import BrowserChrome, { type ChromeHandle, type Panels } from "@/components/BrowserChrome";
import BrowserViewport from "@/components/BrowserViewport";
import AnswerPanel from "@/components/CommandBar";
import DreamBackground from "@/components/DreamBackground";
import ObsidianPane from "@/components/ObsidianPane";
import { useRecall } from "@/lib/useRecall";

export default function Home() {
  const s = useRecall();
  const chrome = useRef<ChromeHandle>(null);
  const [electron, setElectron] = useState(false);
  const [panels, setPanels] = useState<Panels>({ recall: false, vault: false });
  const toggle = (p: keyof Panels) => setPanels((v) => ({ ...v, [p]: !v[p] }));

  useEffect(() => setElectron(navigator.userAgent.includes("Electron")), []);

  // browser-style shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      const k = e.key.toLowerCase();
      const active = s.tabs.find((t) => t.active);
      if (k === "l" || k === "k") { e.preventDefault(); chrome.current?.focusOmnibox(); }
      else if (k === "t") { e.preventDefault(); s.newTab(); setTimeout(() => chrome.current?.focusOmnibox(), 300); }
      else if (k === "w" && active) { e.preventDefault(); s.closeTab(active.id); }
      else if (k === "j") { e.preventDefault(); toggle("recall"); }
      else if (k === "b") { e.preventDefault(); toggle("vault"); }
      else if (k === "r") { e.preventDefault(); s.send({ type: "input", kind: "reload" }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s]);

  const dock = panels.recall || panels.vault;

  return (
    <main className="relative flex h-screen flex-col overflow-hidden">
      <DreamBackground />
      <BrowserChrome ref={chrome} s={s} panels={panels} toggle={toggle} onRecall={() => setPanels((v) => ({ ...v, recall: true }))} electron={electron} />

      <div className="flex min-h-0 flex-1 gap-2 p-2">
        <div className="min-w-0 flex-1">
          <BrowserViewport s={s} />
        </div>
        {dock && (
          <aside className="dock-in flex w-[420px] shrink-0 flex-col gap-2">
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
    </main>
  );
}
