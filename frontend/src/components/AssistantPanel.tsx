"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, AtSign, CheckCircle2, CircleAlert, Clock3, ExternalLink, History, Loader2, MousePointer2, Phone, Play, Sparkles, UserRound, X, Zap } from "lucide-react";
import type { RecallState } from "@/lib/useRecall";
import { API, type TaskStep } from "@/lib/types";
import SpotlightCard from "./reactbits/SpotlightCard";

type Task = {
  people: { name: string; role: string; recent: { title: string; url: string; when: string | null }[] }[];
  opened: string | null; results: { title: string; url: string; snippet: string; providers: string[] }[];
  contacts: { type: "email" | "phone" | "profile"; value: string; source: string }[]; ok: boolean; status?: string; error?: string;
  vault_only?: boolean; namesake_warning?: boolean;
};
type Entry =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "recall"; rid: string }
  | { id: string; role: "task"; tid: string; task: Task | null }
  | { id: string; role: "note"; text: string; error?: boolean };

const SUGGESTIONS = [
  "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours",
  "the proposal method section we revised with Priya Raman eight days ago",
  "the formula sheet I had open last night for Rostova's quiz",
  "find contact info for the authors of the Welch and Bishop Kalman filter tutorial",
];

const host = (u: string) => { try { return new URL(u, "http://x").hostname.replace(/^www\./, "") || u; } catch { return u; } };
const when = (ts?: string | null) => (ts ? new Date(ts).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "");
const uid = () => Math.random().toString(36).slice(2, 10);

function A({ href, children }: { href: string; children: React.ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-700 underline-offset-2 hover:text-orange-600 hover:underline">{children}<ExternalLink size={10} className="shrink-0 opacity-60" /></a>;
}

/** The recall answer: the memory as a link, what changed, and Telem sources, nothing else. */
function RecallCard({ s, rid }: { s: RecallState; rid: string }) {
  const r = s.result?.rid === rid ? s.result : null;
  if (!r) return <p className="flex items-center gap-2 text-[13px] text-sky-900/70"><Loader2 size={14} className="animate-spin text-orange-500" />Finding it and taking you there…</p>;
  const ep = !r.ambiguous ? r.episode : null;
  const ch = s.changes && ep && s.changes.note_id === ep.id ? s.changes : null;
  const t = s.telem && s.telem.rid === rid ? s.telem : null;
  if (r.ambiguous && s.ambiguity?.rid === rid) return <div>
    <p className="text-[13px] font-medium text-sky-950">Two memories match equally well. Which one?</p>
    <div className="mt-2 space-y-1.5">{s.ambiguity.candidates.map((c) => <button key={c.id} disabled={s.running} onClick={() => s.choose(rid, c.id)}
      className="w-full rounded-xl bg-white px-3 py-2 text-left text-[13px] shadow-[inset_0_0_0_1px_rgba(2,121,179,.15)] transition hover:shadow-[inset_0_0_0_1.5px_rgba(252,115,77,.7)] disabled:opacity-50">
      <span className="font-medium text-sky-950">{c.title.replace(/^Opened /, "")}</span>
      <span className="mt-0.5 flex items-center gap-1 text-[11px] text-sky-900/55"><Clock3 size={11} />{when(c.timestamp)}</span>
    </button>)}</div>
  </div>;
  if (r.ambiguous) return <p className="text-[13px] text-sky-900/70">Picked one; restoring it…</p>;
  if (!ep) return <p className="text-[13px] text-sky-900/70">I couldn&apos;t find a matching memory. Try adding who or when.</p>;
  return <div className="space-y-2">
    <div>
      <p className="text-[14px] font-semibold leading-snug text-sky-950">{ep.title.replace(/^(Reviewed|Opened|Read|Had) (the )?/, "")}</p>
      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11.5px] text-sky-900/60"><span className="flex items-center gap-1"><Clock3 size={11} />{when(ep.timestamp)}</span>{ep.people.slice(0, 2).map((p) => <span key={p} className="flex items-center gap-1"><UserRound size={11} />{p}</span>)}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12px]">
        {ep.url && <A href={ep.url}>{host(ep.url)}{ep.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 32)}</A>}
        <button onClick={() => s.replayNote(ep.id)} className="flex items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-800 hover:bg-sky-200"><Play size={10} />Take me there again</button>
      </div>
    </div>
    {ch?.status === "changed" && <div className="rounded-xl bg-orange-50 px-2.5 py-2 text-[12px] text-orange-900">
      <span className="font-semibold">Edited since you saw it{ch.edited_by ? ` by ${ch.edited_by}` : ""}:</span>{" "}
      {ch.changes?.slice(0, 3).map((c, i) => <span key={i} className="mr-1.5 font-mono"><del className="text-rose-600">{c.before}</del>→<b className="text-emerald-700">{c.after}</b></span>)}
      {ch.before && <button onClick={() => s.setSnapshotOpen(true)} className="ml-1 inline-flex items-center gap-1 font-medium text-orange-700 underline"><History size={11} />old version</button>}
    </div>}
    {t?.verdict && t.verdict.status !== "context_only" && <p className="text-[12px] leading-snug text-sky-950/80"><Zap size={11} className="mr-1 inline text-orange-500" fill="currentColor" />{t.verdict.headline}</p>}
    {t && !t.verdict && <p className="flex items-center gap-1.5 text-[11.5px] text-sky-900/55"><Loader2 size={11} className="animate-spin" />Checking sources with Telem…</p>}
    {t?.verdict && t.verdict.citations.length > 0 && <ul className="space-y-0.5 text-[12px]">{t.verdict.citations.map((c) => <li key={c.id} className="truncate"><A href={c.url}>{c.title || host(c.url)}</A></li>)}</ul>}
  </div>;
}

function Steps({ steps }: { steps: TaskStep[] }) {
  return <ol className="space-y-1">{steps.map((st, i) => <li key={i} className="flex items-start gap-2 text-[12px] leading-snug">
    <span className="mt-0.5 shrink-0">{st.state === "run" ? <Loader2 size={12} className="animate-spin text-orange-500" /> : st.state === "warn" ? <CircleAlert size={12} className="text-orange-600" /> : <CheckCircle2 size={12} className="text-emerald-600" />}</span>
    <span className={st.state === "run" ? "font-medium text-sky-950" : "text-sky-900/70"}>{st.text}</span>
  </li>)}</ol>;
}

function TaskCard({ task, steps }: { task: Task | null; steps: TaskStep[] }) {
  if (!task) return <div className="space-y-2">
    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-orange-600"><MousePointer2 size={12} />Taking over your browser</p>
    {steps.length ? <Steps steps={steps} /> : <p className="flex items-center gap-2 text-[12.5px] text-sky-900/65"><Loader2 size={13} className="animate-spin text-orange-500" />Working on it…</p>}
  </div>;
  return <div className="space-y-2.5 text-[12.5px]">
    {steps.length > 0 && <details className="text-sky-900/60"><summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider">What I did ({steps.length} steps)</summary><div className="mt-1.5"><Steps steps={steps} /></div></details>}
    {task.opened && <p className="text-sky-900/75">Opened <A href={task.opened}>{host(task.opened)}</A> in the browser.</p>}
    {task.people.map((p) => <div key={p.name} className="rounded-xl bg-sky-50 px-2.5 py-2">
      <p className="font-semibold text-sky-950">{p.name}</p>
      {p.role && <p className="text-[11.5px] text-sky-900/70">{p.role}</p>}
      {p.recent.length > 0 && <ul className="mt-1 space-y-0.5">{p.recent.map((e) => <li key={e.url} className="truncate text-[11.5px]"><A href={e.url}>{e.title}</A></li>)}</ul>}
    </div>)}
    {task.contacts.length > 0 && <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-sky-900/50">Contacts found</p>
      <ul className="space-y-1">{task.contacts.map((c) => <li key={c.value} className="flex items-center gap-1.5">
        {c.type === "email" ? <AtSign size={12} className="text-orange-500" /> : c.type === "phone" ? <Phone size={12} className="text-orange-500" /> : <UserRound size={12} className="text-orange-500" />}
        {c.type === "email" ? <a href={`mailto:${c.value}`} className="text-sky-700 hover:text-orange-600">{c.value}</a> : c.type === "phone" ? <span className="font-mono text-sky-950">{c.value}</span> : <A href={c.value}>{c.value.replace(/^https?:\/\/(www\.)?/, "").slice(0, 40)}</A>}
        <span className="truncate text-[10.5px] text-sky-900/45">· {host(c.source)}</span>
      </li>)}</ul>
    </div>}
    {task.namesake_warning && <p className="rounded-lg bg-orange-50 px-2 py-1 text-[11.5px] text-orange-800">Web results may be a different person with the same name. Your vault history above is the reliable part.</p>}
    {task.vault_only ? null : task.results.length > 0 ? <ul className="space-y-1.5">{task.results.map((r) => <li key={r.url}>
      <A href={r.url}>{r.title}</A>
      {r.snippet && <p className="line-clamp-2 text-[11.5px] leading-snug text-sky-900/60">{r.snippet}</p>}
    </li>)}</ul> : <p className="text-orange-700">{task.ok ? "No results found." : `Web search unavailable (${task.status}${task.error ? `: ${task.error}` : ""}).`}</p>}
  </div>;
}

export default function AssistantPanel({ s, onClose }: { s: RecallState; onClose: () => void }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  // recalls started anywhere (omnibox, new-tab page, this panel) land here as a card
  const rid = s.result?.rid;
  const original = s.result?.resolved?.original;
  useEffect(() => {
    if (!rid) return;
    setEntries((es) => {
      if (es.some((e) => e.role === "recall" && e.rid === rid)) return es;
      const last = [...es].reverse().find((e) => e.role === "user");
      const add: Entry[] = last && last.role === "user" && last.text === original ? [] : [{ id: uid(), role: "user", text: original ?? "" }];
      return [...es, ...add, { id: uid(), role: "recall", rid }];
    });
  }, [rid, original]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [entries, s.telem, s.changes]);
  useEffect(() => { input.current?.focus(); }, []);

  const send = async (msg: string) => {
    const m = msg.trim();
    if (!m || busy) return;
    setText("");
    const tid = uid();
    const pendingId = uid();
    setEntries((es) => [...es, { id: uid(), role: "user", text: m }, { id: pendingId, role: "task", tid, task: null }]);
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/assistant`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: m, task_id: tid }) });
      if (!r.ok) throw new Error(((await r.json().catch(() => null)) as { detail?: string } | null)?.detail || `HTTP ${r.status}`);
      const res = await r.json();
      // a task fills its card in place; a recall drops the placeholder (its card arrives over the WebSocket)
      setEntries((es) => res.kind === "task"
        ? es.map((e) => (e.id === pendingId ? { ...e, task: res as Task } as Entry : e))
        : es.filter((e) => e.id !== pendingId));
    } catch (e) {
      setEntries((es) => [...es.filter((x) => x.id !== pendingId), { id: uid(), role: "note", text: e instanceof Error ? e.message : String(e), error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return <section className="glass-strong flex h-full min-h-0 flex-col overflow-hidden rounded-[22px] text-sky-950">
    <header className="flex items-center gap-2 border-b border-sky-100 px-4 py-3">
      <Sparkles size={16} className="text-orange-500" />
      <h2 className="flex-1 text-[14px] font-semibold">Assistant</h2>
      {entries.length > 0 && <button onClick={() => setEntries([])} className="rounded-lg px-2 py-1 text-[11px] text-sky-900/55 hover:bg-white">Clear</button>}
      <button onClick={onClose} aria-label="Close assistant" className="rounded-lg p-1 text-sky-900/60 hover:bg-white"><X size={16} /></button>
    </header>

    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
      {entries.length === 0 && <div className="space-y-2">
        <p className="text-[13px] text-sky-900/70">Ask me to bring back something you saw, or to do something on the web: find people, contacts, papers.</p>
        {SUGGESTIONS.map((q) => <button key={q} onClick={() => send(q)} className="block w-full rounded-xl bg-white/80 px-3 py-2 text-left text-[12.5px] text-sky-900 shadow-[inset_0_0_0_1px_rgba(2,121,179,.12)] transition hover:bg-white hover:text-orange-600">{q}</button>)}
      </div>}
      {entries.map((e) => e.role === "user"
        ? <div key={e.id} className="ml-8 rounded-2xl rounded-br-md bg-sky-500 px-3 py-2 text-[13px] text-white shadow-[0_6px_16px_-10px_rgba(2,121,179,.9)]">{e.text}</div>
        : e.role === "note"
          ? <p key={e.id} className={`text-[12.5px] ${e.error ? "text-orange-700" : "text-sky-900/70"}`}>{e.text}</p>
          : <SpotlightCard key={e.id} theme="light" spotlightColor="rgba(252, 115, 77, 0.16)" className="mr-4 !rounded-2xl !rounded-bl-md !bg-white/90 !p-3">
            {e.role === "recall" ? <RecallCard s={s} rid={e.rid} /> : <TaskCard task={e.task} steps={s.taskSteps[e.tid] ?? []} />}
          </SpotlightCard>)}
      <div ref={end} />
    </div>

    <form className="border-t border-sky-100 p-3" onSubmit={(e) => { e.preventDefault(); send(text); }}>
      <div className="glass-input flex items-end gap-2 rounded-2xl px-3 py-2">
        <textarea ref={input} value={text} rows={1} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
          placeholder="Recall something, or ask me to find people, contacts…" aria-label="Message the assistant"
          className="max-h-32 min-h-[22px] flex-1 resize-none bg-transparent text-[13px] leading-snug text-sky-950 outline-none placeholder:text-sky-900/40" />
        <button type="submit" disabled={!text.trim() || busy} aria-label="Send" className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-orange-500 text-white shadow-[0_4px_12px_-4px_rgba(252,115,77,.9)] disabled:opacity-40"><ArrowUp size={16} /></button>
      </div>
    </form>
  </section>;
}
