"use client";

import { motion, useInView } from "motion/react";
import { useRef, useEffect, useState } from "react";

interface NumberTickerProps {
  value: number;
  className?: string;
  duration?: number;
}

export function NumberTicker({
  value,
  className,
  duration = 1.5,
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (!inView) return;

    const startTime = performance.now();
    const from = 0;
    const to = value;

    function animate(time: number) {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / (duration * 1000), 1);

      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(from + (to - from) * eased);

      setDisplayed(current);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    }

    requestAnimationFrame(animate);
  }, [inView, value, duration]);

  return (
    <span ref={ref} className={className}>
      {displayed}
    </span>
  );
}
