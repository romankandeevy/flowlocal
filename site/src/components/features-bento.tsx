"use client";

import { BlurFade } from "@/components/blur-fade";
import {
  Eraser,
  CornerUpLeft,
  Zap,
  Palette,
  Mic,
  Undo2,
} from "lucide-react";

const features = [
  {
    title: "Слова-паразиты убираются без модели",
    description:
      '«Ну вот, короче, я думаю, типа, надо сделать» → «Я думаю, надо сделать». Ноль мегабайт, ноль задержки — и ни одного шанса потерять слово: мы ничего не сочиняем, только вычёркиваем.',
    icon: Eraser,
  },
  {
    title: "Понимает поправки на ходу",
    description:
      '«Встреча в пятницу, нет, в субботу» → останется суббота. Работает на вашем компьютере, ставится одной кнопкой.',
    icon: CornerUpLeft,
  },
  {
    title: "Короткие фразы заводятся сами",
    description:
      "Программа замечает, что вы повторяете, и предлагает дать этому короткую фразу. Имя придумываете вы — только вы знаете, «моя почта» это или «рабочая».",
    icon: Zap,
  },
  {
    title: "Тон под приложение",
    description:
      "В почте строже, в чате свободнее. Правило на программу, а не общий переключатель.",
    icon: Palette,
  },
  {
    title: "Правка голосом",
    description:
      "Выделите текст, зажмите сочетание, скажите «сделай короче» — выделенное заменится.",
    icon: Mic,
  },
  {
    title: "Отмена вставки",
    description:
      "Своим сочетанием, ровно то, что вставилось. И только если вы после этого ничего не печатали — иначе это была бы уже ваша работа.",
    icon: Undo2,
  },
];

export function FeaturesBento() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[820px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Речь → <em>правильный</em> текст
          </h2>
          <p className="mt-2 text-secondary">
            Распознать — половина дела. Дальше начинается то, за что конкуренты
            берут 15 долларов в месяц.
          </p>
        </BlurFade>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <BlurFade key={feature.title} delay={i * 0.08}>
              <div className="flex h-full flex-col rounded-[var(--radius-lg)] border border-border bg-paper p-5">
                <feature.icon className="mb-3 size-5 text-accent" />
                <h3 className="text-sm font-medium">{feature.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {feature.description}
                </p>
              </div>
            </BlurFade>
          ))}
        </div>
      </div>
    </section>
  );
}
