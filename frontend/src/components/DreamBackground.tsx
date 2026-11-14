"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import GhostFibers from "@/components/reactbits/GhostFibers";
import Lightfall from "@/components/reactbits/Lightfall";
import LightPillar from "@/components/reactbits/LightPillar";

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

type Variant = "fibers" | "lightfall" | "pillar";

/**
 * Dreamscape backdrop built from React Bits backgrounds (Lightfall by default; ?bg=fibers or ?bg=pillar
 * to compare), a three.js star field, and a soft dark veil behind the headline so text always stays readable.
 */
export default function DreamBackground() {
  const [variant, setVariant] = useState<Variant>("lightfall");
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("bg");
    if (v === "lightfall" || v === "pillar" || v === "fibers") setVariant(v);
  }, []);

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#02070A]" aria-hidden="true">
      <div className="absolute inset-0 bg-[radial-gradient(90%_60%_at_50%_0%,#062d4d_0%,#03131f_45%,#02070A_78%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(70%_40%_at_50%_105%,rgba(252,115,77,.32)_0%,rgba(252,115,77,.08)_45%,transparent_75%)]" />
      <Starfield />
      <div className="absolute inset-0">
        {variant === "fibers" && (
          <GhostFibers
            glowColor="#0297DE"
            secondaryColor="#FC734D"
            lineColor="#cfeeff"
            gradient="along"
            speed={0.35}
            rotation={14}
            rollSpeed={0.1}
            layers={3}
            threads={96}
            density={1.1}
            thickness={1.5}
            glow={1.2}
            brightness={1.7}
            depthOfField={0.7}
            particles={0.6}
            sparkle={0.4}
            vignette={0.45}
            grain={0.04}
            mouseInteraction={false}
            pulseOnClick={false}
          />
        )}
        {variant === "lightfall" && (
          <Lightfall
            colors={["#0297DE", "#5fc4f2", "#FC734D", "#ffffff"]}
            backgroundColor="#0297DE"
            backgroundGlow={0.18}
            speed={0.25}
            streakCount={2}
            density={0.55}
            glow={0.8}
            bloom={0.4}
            opacity={0.85}
            mouseInteraction={false}
            holdToWarp={false}
          />
        )}
        {variant === "pillar" && (
          <LightPillar topColor="#0297DE" bottomColor="#FC734D" intensity={0.85} glowAmount={0.0016} pillarRotation={0}
            quality="low" interactive={false} clickPulse={false} mixBlendMode="screen" />
        )}
      </div>
      {/* readability veil behind the headline + edge vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(42%_26%_at_50%_16%,rgba(2,7,10,.72)_0%,rgba(2,7,10,.35)_55%,transparent_100%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_50%_45%,transparent_50%,rgba(2,7,10,.85)_100%)]" />
    </div>
  );
}
