"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  API,
  WS_URL,
  type AgentEvent,
  type BBox,
  type Candidate,
  type Changes,
  type Enrichment,
  type NodeScore,
  type GraphData,
  type RecallResult,
  type Status,
  type Telemetry,
  type TraceStep,
} from "./types";

export type RecallState = ReturnType<typeof useRecall>;

export function useRecall() {
  const wsRef = useRef<WebSocket | null>(null);
  const frameUrl = useRef<string | null>(null);
  const [frame, setFrame] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [cursor, setCursor] = useState<{ x: number; y: number; click?: boolean } | null>(null);
  const [bbox, setBBox] = useState<BBox | null>(null);
  const [agent, setAgent] = useState<AgentEvent | null>(null);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [enrichment, setEnrichment] = useState<Enrichment | null>(null);
  const [result, setResult] = useState<RecallResult | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [nodeScores, setNodeScores] = useState<Record<string, NodeScore>>({});
  const [topId, setTopId] = useState<string | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [ambiguousIds, setAmbiguousIds] = useState<string[]>([]);
  const [queryLabel, setQueryLabel] = useState<string | null>(null);
  const [ambiguity, setAmbiguity] = useState<{ rid: string; margin: number; threshold: number; candidates: Candidate[] } | null>(null);
  const [changes, setChanges] = useState<Changes | null>(null);
  const [lastOpts, setLastOpts] = useState({ replay: true, enrich: true });
  const [graph, setGraph] = useState<GraphData>({ nodes: [], links: [] });
  const [graphVersion, setGraphVersion] = useState(0);
  const [focusNote, setFocusNote] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recorded, setRecorded] = useState(0);
  const [history, setHistory] = useState<{ query: string; title: string; score: number }[]>([]);

  const loadGraph = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/graph`);
      if (r.ok) {
        setGraph(await r.json());
        setGraphVersion((v) => v + 1);
      }
    } catch {
      /* backend offline - connection badge already shows it */
    }
  }, []);

  useEffect(() => {
    let stop = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = "blob";
      wsRef.current = ws;
      ws.onopen = () => {
        setConnected(true);
        loadGraph();
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stop) retry = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (ev) => {
        if (typeof ev.data !== "string") {
          const next = URL.createObjectURL(ev.data as Blob);
          const prev = frameUrl.current;
          frameUrl.current = next;
          setFrame(next);
          if (prev) setTimeout(() => URL.revokeObjectURL(prev), 1000);
          return;
        }
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
          case "status":
            setStatus(msg as Status);
            break;
          case "url":
            setUrl(msg.url);
            setTitle(msg.title ?? "");
            setBBox(null);
            setChanges(null);
            break;
          case "cursor":
            setCursor({ x: msg.x, y: msg.y, click: msg.click });
            break;
          case "bbox":
            setBBox(msg as BBox);
            break;
          case "agent":
            setAgent(msg as AgentEvent);
            break;
          case "recall_start":
            setTrace([{ step: "start", title: "Recall query received", detail: `"${msg.query}"`, t_ms: 0 }]);
            setEnrichment(null);
            setBBox(null);
            setChanges(null);
            setAmbiguity(null);
            setAmbiguousIds([]);
            setPath([]);
            setTopId(null);
            break;
          case "trace":
            setTrace((t) => [...t, msg as TraceStep]);
            break;
          case "graph_scores":
            setScores(msg.scores ?? {});
            setNodeScores(msg.node_scores ?? {});
            setTopId(msg.top ?? null);
            setPath(msg.path ?? []);
            setAmbiguousIds(msg.ambiguous ?? []);
            setQueryLabel(msg.query_label ?? null);
            if (msg.top) setAmbiguity(null); // the answer card shows the memory; the vault stays a clean graph
            break;
          case "ambiguous":
            setAmbiguity({ rid: msg.rid, margin: msg.margin, threshold: msg.threshold, candidates: msg.candidates });
            break;
          case "changes":
            setChanges(msg as Changes);
            break;
          case "enrichment":
            setEnrichment(msg as Enrichment);
            break;
          case "telemetry":
            setTelemetry(msg as Telemetry);
            break;
          case "result":
            setResult(msg as RecallResult);
            break;
          case "graph_update":
            loadGraph();
            if (msg.focus) setFocusNote(msg.focus);
            break;
          case "recorded":
            setRecorded(msg.buffer ?? 0);
            break;
          case "browser_error":
            setError(msg.message);
            break;
        }
      };
    };
    connect();
    return () => {
      stop = true;
      if (retry) clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [loadGraph]);

  const send = useCallback((obj: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  const recall = useCallback(
    async (query: string, opts: { replay: boolean; enrich: boolean }) => {
      setRunning(true);
      setError(null);
      setLastOpts(opts);
      try {
        const r = await fetch(`${API}/api/recall`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ query, ...opts }),
        });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`);
        const res = (await r.json()) as RecallResult;
        setResult(res);
        const top = res.search.results[0];
        if (top) setHistory((h) => [{ query, title: top.title, score: top.score }, ...h].slice(0, 6));
        return res;
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return null;
      } finally {
        setRunning(false);
      }
    },
    [],
  );

  const choose = useCallback(
    async (rid: string, id: string) => {
      setRunning(true);
      setError(null);
      try {
        const r = await fetch(`${API}/api/recall/choose`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ rid, id, ...lastOpts }),
        });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`);
        setAmbiguity(null);
        setResult((await r.json()) as RecallResult);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setRunning(false);
      }
    },
    [lastOpts],
  );

  const capture = useCallback(async () => {
    const r = await fetch(`${API}/api/episode/capture`, { method: "POST" });
    if (!r.ok) {
      setError((await r.json().catch(() => ({}))).detail ?? "capture failed");
      return null;
    }
    setRecorded(0);
    return r.json();
  }, []);

  const replayNote = useCallback(async (id: string) => {
    const r = await fetch(`${API}/api/replay/${encodeURIComponent(id)}`, { method: "POST" });
    if (!r.ok) setError((await r.json().catch(() => ({}))).detail ?? "replay failed");
  }, []);

  return {
    connected, status, frame, url, title, cursor, bbox, agent, trace, telemetry, enrichment, result,
    scores, nodeScores, topId, path, ambiguousIds, queryLabel, ambiguity, changes,
    graph, graphVersion, focusNote, setFocusNote, running, error, setError, recorded, history,
    send, recall, choose, capture, replayNote, loadGraph,
  };
}
