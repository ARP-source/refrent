"use client";
import type { RecallState } from "@/lib/useRecall";
import { Clock3, Hand, UserRound, X } from "lucide-react";

export default function AmbiguityDialog({ s, onClose }: { s: RecallState; onClose: () => void }) {
  const a = s.ambiguity;
  if (!a) return null;
  return <div role="dialog" aria-modal="true" aria-labelledby="ambiguity-title" className="absolute inset-0 z-40 grid place-items-center bg-sky-200/45 p-8 backdrop-blur-md">
    <section className="glass-strong w-full max-w-4xl rounded-3xl p-7 text-sky-950">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-2xl bg-orange-100 text-orange-600"><Hand size={20} /></span>
        <div className="flex-1">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-orange-600">Ambiguous reference detected · ΔP = {a.margin.toFixed(2)}</div>
          <h2 id="ambiguity-title" className="font-serif text-3xl leading-tight">Two memories. I won’t guess.</h2>
        </div>
        <button onClick={onClose} aria-label="Close memory choices" className="rounded-lg p-2 hover:bg-sky-100"><X /></button>
      </div>
      <p className="mt-3 text-sm text-sky-900/75">The top candidates are only <strong className="text-orange-600">{(a.margin * 100).toFixed(1)}%</strong> apart, below the {(a.threshold * 100).toFixed(0)}% confidence margin. Which one did you mean?</p>
      <div className="mt-6 grid grid-cols-2 gap-4">{a.candidates.map((c, index) => <button autoFocus={index === 0} disabled={s.running} key={c.id} onClick={() => s.choose(a.rid, c.id)}
        className="group rounded-2xl bg-white/85 p-5 text-left shadow-[inset_0_0_0_1px_rgba(2,121,179,.15),0_10px_30px_-18px_rgba(2,121,179,.6)] transition hover:-translate-y-0.5 hover:bg-white hover:shadow-[inset_0_0_0_2px_rgba(252,115,77,.6),0_16px_40px_-18px_rgba(252,115,77,.6)] disabled:opacity-50">
        <p className="text-lg font-semibold">{c.title.replace(/^Opened /, "")}</p>
        <p className="mt-3 flex items-center gap-1.5 text-sm text-sky-800"><Clock3 size={14} />{c.timestamp ? new Date(c.timestamp).toLocaleString() : "Timestamp unavailable"}</p>
        {c.people.length > 0 && <p className="mt-1.5 flex items-center gap-1.5 text-xs text-sky-900/60"><UserRound size={13} />{c.people.join(" · ")}</p>}
        <div className="mt-3 rounded-xl bg-sky-50 p-3"><p className="line-clamp-3 text-sm text-sky-950/80">{c.excerpt}</p></div>
        <p className="mt-4 text-sm font-semibold text-sky-600 group-hover:text-orange-600">Restore this memory →</p>
      </button>)}</div>
    </section>
  </div>;
}
