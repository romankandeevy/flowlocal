"use client";

import { motion } from "motion/react";
import { Download, Github } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="relative overflow-hidden px-4 pb-16 pt-20 text-center sm:pt-28">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
          backgroundSize: "20px 20px",
        }}
      />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-[600px] w-[800px] -translate-x-1/2 rounded-full opacity-[0.08]"
        style={{
          background:
            "radial-gradient(ellipse at center, var(--accent), transparent 70%)",
        }}
      />

      <motion.h1
        className="relative mx-auto max-w-[700px] text-balance text-[clamp(1.875rem,5.4vw,3.25rem)] font-bold leading-[1.08] tracking-[-0.03em]"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        Диктовка, которая работает
        <br />
        без интернета
      </motion.h1>

      <motion.p
        className="relative mx-auto mt-5 max-w-[620px] text-balance text-secondary"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        style={{ fontSize: "17px" }}
      >
        Зажали клавишу — говорите. Отпустили — текст уже в том окне, где вы и
        печатали. Голос не покидает этот компьютер: не потому что мы обещаем, а
        потому что некуда.
      </motion.p>

      <motion.div
        className="relative mt-7 flex flex-wrap justify-center gap-2.5"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <Button asChild>
          <a href="https://github.com/romankandeevy/flowlocal/releases/latest">
            <Download className="h-4 w-4" />
            Скачать для Windows
          </a>
        </Button>
        <Button variant="outline" asChild>
          <a href="https://github.com/romankandeevy/flowlocal">
            <Github className="h-4 w-4" />
            Исходный код
          </a>
        </Button>
      </motion.div>

      <motion.p
        className="relative mx-auto mt-4 text-xs text-muted"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.45 }}
      >
        70 МБ · без прав администратора · бесплатно и с открытым кодом
      </motion.p>
    </section>
  );
}
