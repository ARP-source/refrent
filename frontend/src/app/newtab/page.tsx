"use client";

import { useEffect, useRef, useState } from "react";
import { Clock3, Search, Sparkles, UserRound } from "lucide-react";
import DreamBackground from "@/components/DreamBackground";
import BlurText from "@/components/reactbits/BlurText";
import GlassSurface from "@/components/reactbits/GlassSurface";
import GradientText from "@/components/reactbits/GradientText";
import ShinyText from "@/components/reactbits/ShinyText";
import SpotlightCard from "@/components/reactbits/SpotlightCard";
import StarBorder from "@/components/reactbits/StarBorder";
import { API } from "@/lib/types";

/**
 * Referent new-tab page. It runs inside the native browsing view as an ordinary web page, so it only uses
 * the engine's same-origin API (/api/notes, /api/recall); the app window follows recalls over its WebSocket.
 */
const DEMOS = [
  ["Find the right guide", "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours"],
  ["Priya's proposal", "the proposal method section we revised with Priya Raman eight days ago"],
  ["Too close to guess", "the formula sheet I had open last night for Rostova's quiz"],
  ["Dana's primer", "the Ito calculus primer I read for Dana Chen's MATH 340"],
] as const;

const TILES = [
  { name: "Canvas", url: "/portals/canvas/", color: "#c2410c", glyph: "C" },
  { name: "Docs", url: "/portals/docs/proposal", color: "#1a73e8", glyph: "D" },
  { name: "Lab Wiki", url: "/portals/wiki/", color: "#0f766e", glyph: "W" },
  { name: "Code", url: "/portals/code/ekf-tracker", color: "#334155", glyph: "</>" },
  { name: "Scholar", url: "https://scholar.google.com/", color: "#4285f4", glyph: "S" },
  { name: "arXiv", url: "https://arxiv.org/", color: "#b31b1b", glyph: "a" },
];

type Episode = { id: string; title: string; type: string; timestamp: string | null; url: string | null; people: string[] };

const looksLikeUrl = (s: string) => !/\s/.test(s) && (/^(https?:\/\/|localhost(:\d+)?|127\.\d+\.\d+\.\d+|\/)/i.test(s) || /^[\w-]+(\.[\w-]+)+(:\d+)?([/?#]\S*)?$/i.test(s));
const ago = (ts: string | null) => {
  if (!ts) return "";
  const d = Math.round((Date.now() - new Date(ts).getTime()) / 86400000);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
};

export default function NewTab() {
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"web" | "recall">("web");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null);
  const [episodes, setEpisodes] = useState<Episode[] | null>(null);
  const [greeting, setGreeting] = useState("");

  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(`${h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"} · ${new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}`);
    fetch(`${API}/api/notes`).then((r) => r.json()).then((notes: Episode[]) => setEpisodes(notes.filter((n) => n.type === "episode" && n.url).slice(0, 6))).catch(() => setEpisodes([]));
    input.current?.focus();
  }, []);

  const recall = async (query: string) => {
    setStatus({ text: "Searching your memory… the browser will take you there." });
    try {
      const r = await fetch(`${API}/api/recall`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query, replay: true, enrich: true }) });
      if (r.status === 409) return setStatus({ text: "A recall is already running. Try again in a moment.", error: true });
      if (!r.ok) return setStatus({ text: `Recall failed: ${(await r.text()).slice(0, 160)}`, error: true });
      const res = await r.json();
      setStatus(res.ambiguous ? { text: "Two memories are too close to call. Pick one in the Referent window." } : null);
    } catch {
      setStatus({ text: "Could not reach the Referent engine. Is it running?", error: true });
    }
  };

  const submit = () => {
    const v = text.trim();
    if (!v) return;
    if (looksLikeUrl(v)) window.location.href = /^(https?:\/\/|\/)/i.test(v) ? v : `${/^(localhost|127\.)/.test(v) ? "http" : "https"}://${v}`;
    else if (mode === "recall") recall(v);
    else window.location.href = `https://www.google.com/search?q=${encodeURIComponent(v)}`;
  };

  return (
    <main className="relative min-h-screen overflow-x-hidden px-6 pb-16 pt-[11vh] text-sky-950">
      <DreamBackground />
      <div className="mx-auto max-w-[880px]">
        <p className="text-center text-sm text-sky-900/60">{greeting || " "}</p>
        <h1 className="mt-1 flex justify-center font-serif text-[clamp(56px,9vw,96px)] leading-none">
          <GradientText colors={["#0b3350", "#0297de", "#fc734d", "#0297de", "#0b3350"]} animationSpeed={10} className="font-serif">Referent.</GradientText>
        </h1>
        <div className="mt-2 flex justify-center">
          <BlurText text="Ask the way you remember it." animateBy="words" delay={90} className="text-[15px] text-sky-900/70" />
        </div>

        <GlassSurface width="100%" height={64} borderRadius={32} brightness={96} opacity={0.92} blur={14} backgroundOpacity={0.55} saturation={1.5} className="mt-7">
          <form className="flex h-full w-full items-center gap-2 px-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <div className="flex shrink-0 rounded-full bg-sky-900/[0.07] p-1 text-[13px]">
              {(["web", "recall"] as const).map((m) => <button key={m} type="button" aria-pressed={mode === m} onClick={() => { setMode(m); input.current?.focus(); }}
                className={`rounded-full px-3.5 py-1.5 font-medium transition ${mode === m ? (m === "recall" ? "bg-orange-500 text-white shadow-[0_4px_14px_-4px_rgba(252,115,77,.8)]" : "bg-white text-sky-950 shadow-sm") : "text-sky-900/60"}`}>{m === "web" ? "Web" : "Recall"}</button>)}
            </div>
            {mode === "recall" ? <Sparkles size={17} className="shrink-0 text-orange-500" /> : <Search size={17} className="shrink-0 text-sky-700/60" />}
            <input ref={input} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
              aria-label={mode === "recall" ? "Ask the way you remember it" : "Search the web or enter a URL"}
              placeholder={mode === "recall" ? "Ask the way you remember it…" : "Search the web or enter a URL"}
              className="h-full min-w-0 flex-1 bg-transparent text-[17px] text-sky-950 outline-none placeholder:text-sky-900/40" />
            <StarBorder as="button" type="submit" theme="light" color={mode === "recall" ? "#fc734d" : "#0297de"} duration={5} radius={999}
              backgroundColor={mode === "recall" ? "#fc734d" : "#0297de"} textColor="#ffffff" className="shrink-0 text-[14px] font-semibold">
              {mode === "recall" ? "Recall" : "Search"}
            </StarBorder>
          </form>
        </GlassSurface>
        <p role="status" className={`mt-3 min-h-5 text-center text-[13px] ${status?.error ? "text-orange-700" : "text-sky-900/65"}`}>{status?.text}</p>

        <div className="mt-2 flex flex-wrap justify-center gap-2">
          {DEMOS.map(([label, query]) => <button key={label} title={query} onClick={() => { setMode("recall"); setText(query); recall(query); }}
            className="rounded-full bg-white/70 px-3.5 py-1.5 text-[12.5px] font-medium text-sky-900 shadow-[inset_0_0_0_1px_rgba(2,121,179,.15)] backdrop-blur transition hover:bg-white hover:text-orange-600 hover:shadow-[inset_0_0_0_1px_rgba(252,115,77,.55)]">
            {label}
          </button>)}
        </div>

        <h2 className="mb-3 mt-12 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-900/45">Shortcuts</h2>
        <nav className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {TILES.map((t) => <a key={t.name} href={t.url} className="block rounded-[20px] transition hover:-translate-y-0.5">
            <SpotlightCard theme="light" spotlightColor="rgba(252, 115, 77, 0.28)" className="flex flex-col items-center gap-2 !rounded-[20px] !bg-white/70 !p-4 backdrop-blur">
              <span className="grid h-11 w-11 place-items-center rounded-[14px] text-[16px] font-semibold text-white" style={{ background: t.color }}>{t.glyph}</span>
              <span className="text-[12.5px] font-medium text-sky-950">{t.name}</span>
            </SpotlightCard>
          </a>)}
        </nav>

        <h2 className="mb-3 mt-10 px-1 text-[11px] font-semibold uppercase tracking-[0.14em]">
          <ShinyText text="Pick up where you left off" color="rgba(11, 51, 80, 0.45)" shineColor="#fc734d" speed={3} />
        </h2>
        <section className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {episodes === null && <p className="px-1 text-[13px] text-sky-900/60">Loading your recent episodes…</p>}
          {episodes?.length === 0 && <p className="px-1 text-[13px] text-sky-900/60">No episodes yet. Browse and capture a view to start your vault.</p>}
          {episodes?.map((e) => <a key={e.id} href={e.url ?? "#"} className="block rounded-[18px] transition hover:-translate-y-0.5">
            <SpotlightCard theme="light" spotlightColor="rgba(2, 151, 222, 0.22)" className="!rounded-[18px] !bg-white/70 !p-4 backdrop-blur">
              <p className="line-clamp-2 text-[14px] font-medium leading-snug text-sky-950">{e.title}</p>
              <p className="mt-1.5 flex items-center gap-3 text-[12px] text-sky-900/60">
                <span className="flex items-center gap-1"><Clock3 size={12} className="text-orange-500" />{ago(e.timestamp)}</span>
                {e.people.length > 0 && <span className="flex items-center gap-1 truncate"><UserRound size={12} />{e.people.slice(0, 2).join(", ")}</span>}
              </p>
            </SpotlightCard>
          </a>)}
        </section>

        <p className="mt-10 text-center text-[12px] text-sky-900/45">Graph-resolved recall · grounded by <b className="font-semibold text-sky-900/70">Telem AI</b></p>
      </div>
    </main>
  );
}
