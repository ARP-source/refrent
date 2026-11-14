"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import Lightfall from "@/components/reactbits/Lightfall";
import LightRays from "@/components/reactbits/LightRays";

/** three.js star field: slow parallax drift of blue/white/orange dust. */
function Starfield() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100);
    camera.position.z = 12;

    const count = 900;
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const palette = [new THREE.Color("#ffffff"), new THREE.Color("#93d8f7"), new THREE.Color("#0297de"), new THREE.Color("#fc734d")];
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 26;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
      const r = Math.random();
      const c = palette[r < 0.55 ? 0 : r < 0.8 ? 1 : r < 0.93 ? 2 : 3];
      col.set([c.r, c.g, c.b], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({ size: 0.045, vertexColors: true, transparent: true, opacity: 0.7, depthWrite: false, blending: THREE.AdditiveBlending });
    const points = new THREE.Points(geo, mat);
    scene.add(points);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = host;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = "100%";
      renderer.domElement.style.height = "100%";
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    resize();

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const clock = new THREE.Clock();
    const tick = () => {
      const t = clock.getElapsedTime();
      points.rotation.y = t * 0.008;
      points.rotation.x = Math.sin(t * 0.05) * 0.03;
      renderer.render(scene, camera);
      if (!reduce) raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      geo.dispose();
      mat.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={ref} className="absolute inset-0" aria-hidden="true" />;
}

/**
 * Daylight dreamscape: pale sky gradient, React Bits light rays falling from the top, drifting
 * cloud glows, a warm orange horizon accent and a faint star/dust field. ?bg=night keeps the old look.
 */
export default function DreamBackground() {
  const [night, setNight] = useState(false);
  useEffect(() => setNight(new URLSearchParams(window.location.search).get("bg") === "night"), []);

  if (night) return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#02070A]" aria-hidden="true">
      <div className="absolute inset-0 bg-[radial-gradient(90%_60%_at_50%_0%,#062d4d_0%,#03131f_45%,#02070A_78%)]" />
      <Starfield />
      <div className="absolute inset-0"><Lightfall colors={["#0297DE", "#5fc4f2", "#FC734D", "#ffffff"]} backgroundColor="#0297DE" backgroundGlow={0.18} speed={0.25} streakCount={2} density={0.55} glow={0.8} bloom={0.4} opacity={0.85} mouseInteraction={false} holdToWarp={false} /></div>
    </div>
  );

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div className="absolute inset-0 bg-[linear-gradient(180deg,#bfe5fb_0%,#dcf1fd_38%,#f3faff_72%,#fff6f0_100%)]" />
      <div className="dream-cloud absolute -left-[10%] top-[18%] h-[55vh] w-[55vw] rounded-full bg-[radial-gradient(closest-side,rgba(255,255,255,.95),rgba(255,255,255,0))]" />
      <div className="dream-cloud absolute -right-[12%] top-[40%] h-[60vh] w-[60vw] rounded-full bg-[radial-gradient(closest-side,rgba(255,255,255,.85),rgba(255,255,255,0))] [animation-delay:-9s]" />
      <div className="absolute inset-x-0 bottom-0 h-[45vh] bg-[radial-gradient(60%_80%_at_70%_110%,rgba(252,115,77,.28)_0%,rgba(252,115,77,.08)_45%,transparent_75%)]" />
      <div className="absolute inset-0 opacity-80 mix-blend-screen">
        <LightRays raysOrigin="top-center" raysColor="#ffffff" raysSpeed={0.6} lightSpread={1.1} rayLength={1.6} fadeDistance={1.1}
          saturation={0.9} followMouse={false} mouseInfluence={0} noiseAmount={0.04} distortion={0.04} />
      </div>
      <div className="absolute inset-0 bg-[radial-gradient(130%_100%_at_50%_40%,transparent_55%,rgba(2,121,179,.12)_100%)]" />
    </div>
  );
}
