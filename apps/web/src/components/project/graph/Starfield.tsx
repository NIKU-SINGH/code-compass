"use client";

import { useEffect, useRef } from "react";
import { resolveCssColor } from "@/lib/cssColor";
import { useColorSchemeVersion } from "./useColorSchemeVersion";

export function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const schemeVersion = useColorSchemeVersion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function draw() {
      const parent = canvas!.parentElement;
      if (!parent) return;
      const { width, height } = parent.getBoundingClientRect();
      canvas!.width = width;
      canvas!.height = height;

      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.46;

      const gradient = ctx!.createRadialGradient(cx, cy, 0, cx, cy, radius);
      gradient.addColorStop(0, resolveCssColor("--card"));
      gradient.addColorStop(1, resolveCssColor("--background"));
      ctx!.fillStyle = gradient;
      ctx!.beginPath();
      ctx!.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx!.fill();

      const star = resolveCssColor("--foreground");
      const starCount = Math.floor((radius * radius) / 900);
      ctx!.fillStyle = star;
      for (let i = 0; i < starCount; i++) {
        const a = Math.random() * Math.PI * 2;
        const r = Math.sqrt(Math.random()) * radius;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r;
        ctx!.globalAlpha = 0.1 + Math.random() * 0.3;
        ctx!.fillRect(x, y, 1, 1);
      }
    }

    draw();
    const observer = new ResizeObserver(draw);
    if (canvas.parentElement) observer.observe(canvas.parentElement);
    return () => observer.disconnect();
  }, [schemeVersion]);

  return <canvas ref={canvasRef} className="absolute inset-0 -z-10" />;
}
