"use client";

import { useRef, useEffect, useState } from "react";
import { useInView } from "motion/react";
import { Play } from "lucide-react";

export function DemoVideo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef, {
    margin: "-100px",
    amount: 0.3,
  });
  const [canPlay, setCanPlay] = useState(false);
  const [userPlayed, setUserPlayed] = useState(false);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (inView && !reduced) {
      el.load();
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [inView]);

  function handleUserPlay() {
    const el = videoRef.current;
    if (!el) return;
    setUserPlayed(true);
    el.muted = false;
    el.play().catch(() => {});
  }

  return (
    <section ref={containerRef} className="px-4 pb-8">
      <figure className="mx-auto max-w-[840px]">
        <div className="overflow-hidden rounded-[var(--radius-xl)] border border-border bg-paper shadow-sm">
          {/* Рамка окна Windows 11 */}
          <div className="flex items-center gap-1.5 border-b border-border bg-fill-subtle px-4 py-2.5">
            <span className="size-3 rounded-full bg-[#e81123]" />
            <span className="size-3 rounded-full bg-[#ffb900]" />
            <span className="size-3 rounded-full bg-[#00cc6a]" />
            <span className="ml-3 text-xs text-muted">FlowLocal — диктовка</span>
          </div>

          {!userPlayed && !canPlay && (
            <button
              onClick={handleUserPlay}
              className="group relative flex aspect-video w-full items-center justify-center bg-neutral-900"
              aria-label="Воспроизвести демо"
            >
              <img
                src="/flowlocal/poster.webp"
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
                onLoad={() => setCanPlay(true)}
              />
              <span className="relative z-10 flex size-16 items-center justify-center rounded-full bg-ink/80 text-paper backdrop-blur-sm transition-transform group-hover:scale-110">
                <Play className="ml-0.5 size-6" />
              </span>
            </button>
          )}

          <video
            ref={videoRef}
            className="aspect-video w-full"
            poster="/flowlocal/poster.webp"
            muted
            loop
            playsInline
            preload="none"
            controls
            onCanPlay={() => setCanPlay(true)}
            style={{ display: userPlayed || canPlay ? "block" : "none" }}
          >
            <source src="/flowlocal/demo.webm" type="video/webm" />
            <source src="/flowlocal/demo.mp4" type="video/mp4" />
          </video>
        </div>

        <figcaption className="mt-2.5 text-center text-xs text-muted">
          Настоящая запись работы: 5 секунд речи распознаны за 0,22 секунды на
          процессоре, вместе с пунктуацией и «10:00».
        </figcaption>
      </figure>
    </section>
  );
}
