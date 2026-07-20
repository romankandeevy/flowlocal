"use client";

import { motion } from "motion/react";
import { useRef } from "react";
import { useInView } from "motion/react";

interface BlurFadeProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

export function BlurFade({ children, className, delay = 0 }: BlurFadeProps) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 16, filter: "blur(4px)" }}
      animate={
        inView
          ? { opacity: 1, y: 0, filter: "blur(0px)" }
          : { opacity: 0, y: 16, filter: "blur(4px)" }
      }
      transition={{
        duration: 0.5,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
