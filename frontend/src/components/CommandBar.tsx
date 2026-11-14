"use client";

import { ChevronDown, ChevronUp, Clock3, FileDiff, Globe, Hand, Loader2, Play, Sparkles, UserRound } from "lucide-react";
import { useState } from "react";
import BorderGlow from "@/components/reactbits/BorderGlow";
import type { RecallState } from "@/lib/useRecall";

function when(ts: string | null | undefined) {
  if (!ts) return "";
  const d = new Date(ts);
  const days = Math.round((Date.now() - d.getTime()) / 86400000);
  const rel = days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} - ${rel}`;
}

/** What a user actually needs after asking: the memory, what changed, and anything new. */
export default function AnswerPanel({ s }: { s: RecallState }) {
  const [drawer, setDrawer] = useState(false);
  const res = s.result;
  const ep = res && !res.ambiguous ? res.episode : null;
  const top = ep ? res!.search.results.find((r) => r.id === ep.id) : null;
  const ch = s.changes && ep && s.changes.note_id === ep.id ? s.changes : null;
  const web = s.enrichment;

  const hints: string[] = [];
  if (res?.resolved.person) hints.push(`${res.resolved.pronouns.join("/")} = ${res.resolved.person.name}`);
  if (res?.resolved.temporal) hints.push(res.resolved.temporal.label);
  if (res?.resolved.anchor_phrase) hints.push(`${res.resolved.anchor_rel} ${res.resolved.anchor_phrase}`);

  return (
    <section className="panel flex min-h-0 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {s.error && <div className="rounded-xl bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{s.error}</div>}

        {!res && !s.running && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-500">
            <Sparkles size={22} className="text-cyan-300/50" />
            <span className="text-[13px]">Ask about something you saw.</span>
          </div>
        )}

        {s.running && !s.ambiguity && (
          <div className="flex items-center gap-2 py-6 text-[13px] text-cyan-100/80">
            <Loader2 size={15} className="animate-spin" /> Searching your memory...
          </div>
        )}

        {/* I won't guess */}
        {s.ambiguity && (
          <div>
            <div className="mb-2 flex items-center gap-2 text-[15px] font-medium text-amber-200">
              <Hand size={16} /> Which one did you mean?
            </div>
            <div className="space-y-2">
              {s.ambiguity.candidates.map((c) => (
                <button
                  key={c.id}
                  disabled={s.running}
                  onClick={() => s.choose(s.ambiguity!.rid, c.id)}
                  className="w-full rounded-2xl bg-amber-400/[0.07] p-3 text-left transition hover:bg-amber-400/[0.14] disabled:opacity-50"
                >
                  <div className="text-[13px] font-medium text-white">{c.title.replace(/^Opened /, "")}</div>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-amber-100/70"><Clock3 size={11} /> {when(c.timestamp)}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* the memory */}
        {ep && top && (
          <BorderGlow key={res!.rid + ep.id} animated backgroundColor="#06121b" borderRadius={18} glowColor="199 98 60" glowRadius={28}
            colors={["#0297DE", "#FC734D", "#5fc4f2"]} fillOpacity={0.3}>
            <div className="p-4">
              <div className="text-[16px] font-medium leading-snug text-white">{ep.title}</div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-slate-400">
                <span className="flex items-center gap-1"><Clock3 size={12} /> {when(ep.timestamp)}</span>
                {ep.people.slice(0, 2).map((p) => <span key={p} className="flex items-center gap-1"><UserRound size={12} /> {p}</span>)}
              </div>
              <p className="mt-2.5 line-clamp-3 text-[13px] leading-relaxed text-slate-300">{top.excerpt}</p>
              <div className="mt-3 flex items-center gap-2">
                <button onClick={() => s.replayNote(ep.id)} className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full bg-cyan-400/15 px-3 py-1.5 text-[12px] text-cyan-100 transition hover:bg-cyan-400/25">
                  <Play size={12} /> Take me there
                </button>
                {hints.length > 0 && <span className="truncate text-[11px] text-slate-500">{hints.join(" - ")}</span>}
              </div>
            </div>
          </BorderGlow>
        )}

        {/* edits since then are shown on the page itself (browser banner); here just a one-line nudge */}
        {ch && ch.status === "changed" && (
          <div className="flex items-center gap-2 px-1 text-[12px] text-orange-200/90">
            <FileDiff size={13} /> Edited since you looked{ch.edited_by ? ` by ${ch.edited_by}` : ""}
          </div>
        )}
      </div>

      {/* new since you last looked */}
      {(web || (s.running && res === null)) && (
        <div className="bg-black/20">
          <button onClick={() => setDrawer((d) => !d)} className="flex w-full items-center gap-2 px-4 py-3 text-left text-[13px]">
            <Globe size={14} className="text-sky-300" />
            <span className="font-medium text-slate-100">New since you last looked</span>
            {web && <span className="rounded-full bg-sky-400/20 px-2 text-[11px] text-sky-100">{web.results.length}</span>}
            <span className="ml-auto text-slate-500">{drawer ? <ChevronDown size={15} /> : <ChevronUp size={15} />}</span>
          </button>
          {drawer && web && (
            <div className="max-h-[34vh] space-y-1 overflow-y-auto px-2 pb-3">
              {web.results.length === 0 && <div className="px-2 text-[12px] text-slate-500">Nothing new found.</div>}
              {web.results.map((r) => (
                <a key={r.url} href={r.url} target="_blank" rel="noreferrer" className="block rounded-xl px-2.5 py-2 transition hover:bg-white/[0.05]">
                  <div className="line-clamp-1 text-[13px] text-slate-100">{r.title}</div>
                  <div className="mt-0.5 flex gap-2 text-[11px] text-slate-500">
                    <span className="truncate">{new URL(r.url).hostname.replace(/^www\./, "")}</span>
                    {r.published && <span>{new Date(r.published).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>}
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
