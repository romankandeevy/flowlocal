"use client";

import { BlurFade } from "@/components/blur-fade";
import { Button } from "@/components/ui/button";
import { Download, BookOpen } from "lucide-react";

export function GetStarted() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[620px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">Поставить</h2>
          <p className="mt-2 text-secondary">
            Windows 10 или 11. Установщик не требует прав администратора и не
            показывает окно UAC. Подписи у него нет, поэтому SmartScreen один
            раз покажет синюю карточку: «Подробнее» → «Выполнить в любом
            случае».
          </p>
        </BlurFade>

        <BlurFade delay={0.1}>
          <div className="mt-6 flex flex-wrap gap-2.5">
            <Button asChild>
              <a href="https://github.com/romankandeevy/flowlocal/releases/latest">
                <Download className="h-4 w-4" />
                Скачать установщик
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://github.com/romankandeevy/flowlocal#readme">
                <BookOpen className="h-4 w-4" />
                Как это устроено
              </a>
            </Button>
          </div>
        </BlurFade>

        <BlurFade delay={0.15}>
          <p className="mt-4 text-xs text-muted">
            После установки нажмите <kbd className="rounded-[var(--radius-sm)] border border-border-strong bg-fill-subtle px-1.5 py-0.5 font-mono text-xs font-medium">Ctrl</kbd> +{" "}
            <kbd className="rounded-[var(--radius-sm)] border border-border-strong bg-fill-subtle px-1.5 py-0.5 font-mono text-xs font-medium">Shift</kbd> +{" "}
            <kbd className="rounded-[var(--radius-sm)] border border-border-strong bg-fill-subtle px-1.5 py-0.5 font-mono text-xs font-medium">Space</kbd> в любом окне и говорите.
          </p>
        </BlurFade>
      </div>
    </section>
  );
}
