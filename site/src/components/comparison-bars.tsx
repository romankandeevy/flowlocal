"use client";

import { useRef } from "react";
import { useInView, motion } from "motion/react";
import { NumberTicker } from "@/components/number-ticker";
import { BlurFade } from "@/components/blur-fade";

function Bar({
  label,
  value,
  color,
  delay,
}: {
  label: string;
  value: number;
  color: string;
  delay: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });

  return (
    <div ref={ref} className="flex items-center gap-3">
      <span className="w-16 shrink-0 text-right text-xs text-muted">{label}</span>
      <div className="relative h-8 flex-1 rounded-[var(--radius-sm)] bg-fill">
        <motion.div
          className={`absolute inset-y-0 left-0 flex items-center justify-end rounded-[var(--radius-sm)] px-2.5 ${color}`}
          initial={{ width: "0%" }}
          animate={inView ? { width: `${value}%` } : { width: "0%" }}
          transition={{
            duration: 1.2,
            delay,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          <span className="text-xs font-medium tabular-nums text-paper">
            <NumberTicker value={Math.round(value)} />
          </span>
        </motion.div>
      </div>
    </div>
  );
}

export function ComparisonBars() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[620px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Почему не Whisper
          </h2>
          <p className="mt-2 text-secondary">
            Все локальные диктовки возят Whisper, а он хорош не на всех языках.
            Мы возим <strong>GigaAM</strong> от SberDevices — 240 миллионов
            параметров, обученных на 700 000 часах русской речи. На русском он{" "}
            <strong>понимает заметно больше слов</strong>.
          </p>
        </BlurFade>

        <BlurFade delay={0.1}>
          <div className="mt-6 rounded-[var(--radius-lg)] border border-border bg-paper p-5">
            <div className="mb-4 flex items-center justify-between gap-4 border-b border-border pb-3 text-xs text-muted">
              <span>Сколько слов из ста распознаётся <strong className="text-ink">правильно</strong></span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2.5 rounded-[3px] bg-ink" />
                  GigaAM
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2.5 rounded-[3px] border border-border-strong bg-fill" />
                  Whisper
                </span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <div className="mb-1.5 text-sm">Русская речь</div>
                <Bar
                  label="GigaAM"
                  value={91.4}
                  color="bg-ink"
                  delay={0}
                />
                <div className="mt-1.5">
                  <Bar
                    label="Whisper"
                    value={83.8}
                    color="bg-fill border border-border"
                    delay={0.2}
                  />
                </div>
              </div>
            </div>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-muted">
            Из ста слов мы разберём девяносто одно, Whisper — восемьдесят
            четыре. То есть ошибок вдвое меньше.
          </p>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Замер не наш и не Сбера: одиннадцать наборов записей, независимый
            стенд, который ведёт автор Vosk — конкурирующей модели, проигравшей
            в этом же сравнении. Свидетельство против собственного интереса, и
            потому мы приводим именно его. Сбер про свою модель сообщает разрыв
            больше нашего, но проверить его нечем, поэтому мы его не повторяем.
          </p>
        </BlurFade>

        <BlurFade delay={0.2}>
          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-[var(--radius-lg)] border border-border bg-paper p-4">
              <div className="font-mono text-xs font-medium uppercase tracking-wider text-muted">
                размер модели
              </div>
              <div className="mt-1.5 text-[30px] font-bold tracking-[-0.03em]">
                236 МБ
              </div>
              <div className="mt-1 text-xs text-muted">
                вместо 1,6 ГБ у Whisper-turbo
              </div>
            </div>
            <div className="rounded-[var(--radius-lg)] border border-border bg-paper p-4">
              <div className="font-mono text-xs font-medium uppercase tracking-wider text-muted">
                видеокарта
              </div>
              <div className="mt-1.5 text-[30px] font-bold tracking-[-0.03em]">
                не нужна
              </div>
              <div className="mt-1 text-xs text-muted">
                на процессоре быстрее, чем Whisper на RTX 4090
              </div>
            </div>
            <div className="rounded-[var(--radius-lg)] border border-border bg-paper p-4">
              <div className="font-mono text-xs font-medium uppercase tracking-wider text-muted">
                в покое
              </div>
              <div className="mt-1.5 text-[30px] font-bold tracking-[-0.03em]">
                ноль
              </div>
              <div className="mt-1 text-xs text-muted">
                пока вы не диктуете, не тратится ни процессор, ни сеть
              </div>
            </div>
          </div>
        </BlurFade>
      </div>
    </section>
  );
}
