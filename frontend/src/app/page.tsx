"use client";

import { AudioLines } from "lucide-react";
import { useEffect, useState } from "react";
import AnswerPanel from "@/components/CommandBar";
import BrowserViewport from "@/components/BrowserViewport";
import DreamBackground from "@/components/DreamBackground";
import HeroPrompt from "@/components/HeroPrompt";
import ObsidianPane from "@/components/ObsidianPane";
import BlurText from "@/components/reactbits/BlurText";
import GradientText from "@/components/reactbits/GradientText";
import { useRecall } from "@/lib/useRecall";

export default function Home() {
  const s = useRecall();
  const [electron, setElectron] = useState(false);
  useEffect(() => setElectron(navigator.userAgent.includes("Electron")), []);

  return (
    <main className="relative flex h-screen flex-col overflow-hidden">
      <DreamBackground />

      {/* minimal top bar - draggable in the desktop app */}
      <div className={`app-drag flex h-11 shrink-0 items-center gap-2 px-5 ${electron ? "pr-[150px]" : ""}`}>
        <AudioLines size={16} className="text-cyan-200" />
        <span className="text-[13px] font-semibold tracking-wide text-white/90">RecallOS</span>
        <span
          title={s.connected ? (s.status?.browser.ready ? "Online" : "Starting") : "Offline"}
          className={`ml-1 h-1.5 w-1.5 rounded-full ${s.connected && s.status?.browser.ready ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : s.connected ? "bg-amber-400" : "bg-rose-400"}`}
        />
      </div>

      {/* hero */}
      <section className="flex shrink-0 flex-col items-center px-6 pb-5 pt-1 text-center">
        <h1 className="mb-5 flex flex-wrap items-baseline justify-center gap-x-3 font-serif text-[52px] leading-none tracking-tight text-white [text-shadow:0_2px_30px_rgba(2,7,10,.9)]">
          <BlurText text="Recall at the speed of" animateBy="words" delay={90} direction="top" trigger="load" className="justify-center" />
          <GradientText colors={["#5fc4f2", "#FC734D", "#ffd9cc", "#0297DE"]} animationSpeed={6} glow={0.45} className="italic">
            thought.
          </GradientText>
        </h1>
        <HeroPrompt s={s} />
      </section>

      {/* workspace */}
      <section className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.3fr)_minmax(0,1.1fr)_minmax(360px,0.9fr)] gap-4 px-5 pb-5">
        <BrowserViewport s={s} />
        <ObsidianPane s={s} />
        <AnswerPanel s={s} />
      </section>
    </main>
  );
}
