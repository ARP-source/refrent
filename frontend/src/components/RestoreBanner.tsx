"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Globe, History, ShieldCheck, X } from "lucide-react";
import type { RecallState } from "@/lib/useRecall";

/** Verified-state + silent-drift strip, rendered directly above the live page. */
export default function RestoreBanner({ s }: { s: RecallState }) {
  const [webOpen, setWebOpen] = useState(false);
  const ch = s.changes;
  const verified = s.agent?.phase === "done" && s.agent.ok === true;
  const web = s.enrichment;
  if (!ch && !web) return null;
  return <div className="glass-strong max-h-[34vh] shrink-0 overflow-auto text-sm text-sky-950">
    {ch && <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
      <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${verified ? "bg-emerald-500 text-white shadow-[0_2px_10px_-3px_rgba(16,185,129,.8)]" : "bg-orange-100 text-orange-700"}`}>
        {verified ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}{verified ? "View verified" : "Restoration needs attention"}
      </span>
      <strong className="font-semibold">{ch.title.replace(/^Reviewed /, "")}</strong>
      <span className="text-xs text-sky-900/60">Section: <code className="font-mono">{ch.selector || "page"}</code> · Snapshot: {ch.seen_at ? new Date(ch.seen_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "unknown"}</span>
    </div>}
    {ch?.status === "changed" && <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50/60 px-4 py-2.5">
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 font-semibold text-orange-700"><AlertTriangle size={16} />Silent edit since you viewed this{ch.edited_by ? ` · edited by ${ch.edited_by}` : ""}</div>
        <div className="flex flex-wrap items-center gap-2 text-[15px]">
          {ch.changes?.slice(0, 5).map((c, i) => <span key={i} className="rounded-lg bg-white/90 px-2 py-0.5 font-mono shadow-[inset_0_0_0_1px_rgba(252,115,77,.25)]"><del className="text-rose-600">{c.before || "∅"}</del><span className="mx-2 text-sky-900/40">→</span><strong className="text-emerald-700">{c.after || "∅"}</strong></span>)}
        </div>
      </div>
      <div className="flex rounded-full bg-white/80 p-1 text-xs font-semibold shadow-[inset_0_0_0_1px_rgba(252,115,77,.25)]">
        <button onClick={() => s.setSnapshotOpen(true)} className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 ${s.snapshotOpen ? "bg-orange-500 text-white" : "text-orange-700 hover:bg-orange-50"}`}><History size={13} />Historical snapshot</button>
        <button onClick={() => s.setSnapshotOpen(false)} className={`rounded-full px-3 py-1.5 ${!s.snapshotOpen ? "bg-sky-500 text-white" : "text-sky-800 hover:bg-sky-50"}`}>Live diff</button>
      </div>
    </div>}
    {ch?.status === "not_found" && <p className="border-t border-orange-200 px-4 py-2 text-orange-700">The saved section could not be verified on this page.</p>}
    {ch?.status === "no_snapshot" && <p className="border-t border-sky-100 px-4 py-2 text-sky-900/70">No historical text snapshot is available for comparison.</p>}
    {web && <div className="border-t border-sky-100">
      <button onClick={() => setWebOpen(!webOpen)} className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-xs text-sky-800 hover:bg-sky-50/70"><Globe size={14} className="text-sky-500" /><strong>{web.results.length} new web sources</strong>{web.published_after ? ` since ${new Date(web.published_after).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : ""} · Telem + Tavily
        <span className="ml-2 flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700"><ShieldCheck size={12} />Privacy guard</span><span className="ml-auto text-orange-600">{webOpen ? "Hide" : "Explore"}</span></button>
      {webOpen && <div className="space-y-2 border-t border-sky-100 px-4 py-3">
        <div className="text-xs font-semibold text-emerald-700">Outbound query stripped of private text · public topic tags only</div>
        <div className="flex flex-wrap gap-2">{web.tags?.map((tag) => <span key={tag} className="rounded-full bg-sky-100 px-2 py-1 text-xs text-sky-900">{tag}</span>)}</div>
        <p className="text-xs text-sky-900/60">Only these allow-listed tags are sent. Document text, people, course codes, and private URLs are excluded.</p>
        <div className="flex flex-wrap gap-3 text-xs">{Object.entries(web.providers).map(([name, p]) => <span key={name} className={p.ok ? "text-emerald-700" : "text-orange-700"}>{name}: {p.ok ? `${p.count} results` : p.status || "unavailable"}{p.error ? ` · ${p.error}` : ""}</span>)}</div>
        {web.results.length === 0 && <p className="text-xs text-sky-900/70">No verified new sources returned. Provider status is shown above.</p>}
        <div className="grid gap-2 md:grid-cols-3">{web.results.map((r) => <a key={r.url} href={r.url} target="_blank" rel="noreferrer" className="rounded-xl bg-white/80 p-3 shadow-[inset_0_0_0_1px_rgba(2,121,179,.12)] hover:bg-white"><div className="text-sm text-sky-950">{r.title}</div><div className="mt-1 text-xs text-sky-900/60">{r.source} · {r.published ? new Date(r.published).toLocaleDateString() : "Publication date unavailable"}</div></a>)}</div>
      </div>}
    </div>}
  </div>;
}

export function HistoricalSnapshot({ s }: { s: RecallState }) {
  if (!s.snapshotOpen || !s.changes?.before) return null;
  return <div role="dialog" aria-modal="true" aria-labelledby="snapshot-title" className="absolute inset-0 z-40 flex items-center justify-center bg-sky-200/50 p-6 backdrop-blur-md">
    <section className="glass-strong max-h-full w-full max-w-4xl overflow-auto rounded-3xl p-7 text-sky-950">
      <div className="flex items-center gap-3"><History className="text-orange-500" /><h2 id="snapshot-title" className="flex-1 font-serif text-2xl">Historical snapshot</h2><button aria-label="Close historical snapshot" onClick={() => s.setSnapshotOpen(false)} className="rounded-lg p-2 hover:bg-sky-100"><X size={20} /></button></div>
      <p className="mt-2 text-sm text-sky-900/70">{s.changes.title} · {s.changes.seen_at ? new Date(s.changes.seen_at).toLocaleString() : "Saved episode"} · <code className="font-mono">{s.changes.selector}</code></p>
      <p className="mt-2 text-xs font-medium text-sky-700">Read-only saved section. The live document has not been modified.</p>
      <div className="mt-6 whitespace-pre-wrap rounded-2xl bg-white p-6 text-lg leading-relaxed text-slate-900 shadow-[inset_0_0_0_1px_rgba(2,121,179,.12)]">{s.changes.before}</div>
      <button autoFocus onClick={() => s.setSnapshotOpen(false)} className="mt-5 rounded-xl bg-sky-500 px-4 py-2 font-semibold text-white shadow-[0_6px_18px_-8px_rgba(2,121,179,.9)] hover:bg-sky-600">Return to live version</button>
    </section>
  </div>;
}
