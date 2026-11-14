"use client";

import { Clock3, Loader2, Search, Sparkles } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import GlassSurface from "@/components/reactbits/GlassSurface";
import StarBorder from "@/components/reactbits/StarBorder";
import type { RecallState } from "@/lib/useRecall";

const SUGGESTIONS = [
  "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours",
  "what is she talking about from 2 weeks ago?",
  "the formula sheet I had open last night for Rostova's quiz",
  "that repo I had open before my Kalman filter broke",
];

export default function HeroPrompt({ s }: { s: RecallState }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // recent searches first, then suggestions; filtered by what is typed
  const items = useMemo(() => {
    const recent = s.history.map((h) => h.query);
    const all = [...new Set([...recent, ...SUGGESTIONS])];
    const needle = q.trim().toLowerCase();
    return all.filter((x) => !needle || x.toLowerCase().includes(needle)).slice(0, 5).map((x) => ({ text: x, recent: recent.includes(x) }));
  }, [s.history, q]);

  const submit = (text = q) => {
    if (!text.trim() || s.running) return;
    setQ(text);
    setOpen(false);
    inputRef.current?.blur();
    s.recall(text.trim(), { replay: true, enrich: true });
  };

  return (
    <div className="relative z-20 w-full max-w-[760px]">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <GlassSurface width="100%" height={58} borderRadius={29} brightness={42} opacity={0.9} blur={12} backgroundOpacity={0.14} saturation={1.4} className="app-nodrag">
          <div className="flex w-full items-center gap-3 pl-4 pr-1">
            {s.running ? <Loader2 size={18} className="shrink-0 animate-spin text-cyan-200" /> : <Search size={18} className="shrink-0 text-cyan-100/70" />}
            <input
              ref={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onFocus={() => setOpen(true)}
              onBlur={() => setTimeout(() => setOpen(false), 150)}
              spellCheck={false}
              placeholder="Ask the way you remember it..."
              className="min-w-0 flex-1 bg-transparent text-[15px] text-white outline-none placeholder:text-slate-400"
            />
            <StarBorder
              type="submit"
              disabled={s.running}
              radius={24}
              color="#FFD9CC"
              trailColor="#FC734D"
              backgroundColor="rgba(252,115,77,0.92)"
              textColor="#ffffff"
              borderColor="rgba(255,255,255,0.25)"
              glow={0.9}
              sparkle
              duration={3.2}
              className="px-5! py-2.5! text-sm font-semibold shadow-[0_0_28px_rgba(252,115,77,.5)]"
            >
              <Sparkles size={14} /> Recall
            </StarBorder>
          </div>
        </GlassSurface>
      </form>

      {open && items.length > 0 && (
        <div className="absolute inset-x-3 top-[64px] overflow-hidden rounded-2xl bg-[#06121b]/90 p-1.5 text-left shadow-[0_30px_60px_-20px_rgba(0,0,0,.9)] backdrop-blur-xl">
          {items.map((it) => (
            <button
              key={it.text}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => submit(it.text)}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-slate-200 transition hover:bg-white/[0.06] hover:text-white"
            >
              {it.recent ? <Clock3 size={13} className="shrink-0 text-slate-500" /> : <Search size={13} className="shrink-0 text-slate-500" />}
              <span className="truncate">{it.text}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
