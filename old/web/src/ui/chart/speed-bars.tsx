// «Быстрее печати в N раз» - полосой, а не только строкой. Две полосы: печать
// и голос, длина каждой - её скорость в словах в минуту. Голос длиннее ровно
// во столько раз, во сколько он быстрее, и это видно глазом, а не считается в
// уме.
//
// Числа - из истории, не из рекламы: печать это TYPING_WPM (оценка набора),
// голос - замер речи человека (stats.speech_wpm). Строка ratio («в 3,0 раза»)
// собрана в Python, там же, где живёт склонение. Здесь только рисуем.
//
// Голос - акцентом (то самое «особенное»: ради этого числа диктовку и завели),
// печать - тихими чернилами. Тени нет: внутри едут полосы, см. card.tsx.

import { t } from "../../i18n";
import { Card } from "../card";
import { cn } from "../cn";
import { useAfterPaint } from "./metric";

export interface SpeedBarsProps {
  /** Оценка скорости набора руками, stats.TYPING_WPM. */
  typingWpm?: number;
  /** Замер речи человека, stats.speech_wpm. */
  voiceWpm: number;
  /** Готовая строка из Python: «в 3,0 раза». Пусто или «-» - строки нет. */
  ratio?: string;
}

export function SpeedBars({
  typingWpm = 40,
  voiceWpm,
  ratio = "",
}: SpeedBarsProps) {
  const grown = useAfterPaint();
  const max = Math.max(1, typingWpm, voiceWpm);

  // Подписи короткие и свои: готовыми списками из Python их не собрать.
  const rows = [
    { name: t("печать"), wpm: typingWpm, accent: false },
    { name: t("голос"), wpm: voiceWpm, accent: true },
  ];

  return (
    <Card shadow={false}>
      <div className="flex flex-col gap-3 px-6 py-4">
        {rows.map((row) => (
          <div key={row.name} className="flex h-[22px] items-center">
            {/* Подпись слева фиксированной ширины - чтобы обе полосы начинались
                от одной вертикали. Иначе «печать» и «голос» разной длины
                сдвигали бы старт, и полосы врали бы длиной. */}
            <span
              className={cn(
                "w-[52px] shrink-0 font-sans text-sm",
                row.accent ? "text-text" : "text-text-muted",
              )}
            >
              {row.name}
            </span>

            {/* Дорожка полосы. Значение стоит в её конце, поэтому трек не
                тянется до правого края, а оставляет место числу. */}
            <div className="h-[10px] min-w-0 flex-1 rounded-full bg-fill">
              <div
                className={cn(
                  "h-full rounded-full transition-[width] ease-out",
                  row.accent ? "bg-accent" : "bg-ink opacity-[0.72]",
                )}
                style={{
                  // Полосы растут от нуля при появлении. Тем же переходом
                  // догоняется и смена данных: до захода на страницу voiceWpm
                  // нулевой, полосы пусты; пришло число - поехали. Одно
                  // правило закрывает оба случая.
                  width: `${grown ? Math.min(1, row.wpm / max) * 100 : 0}%`,
                  transitionDuration: "var(--dur-slow)",
                }}
              />
            </div>

            <span className="w-[76px] shrink-0 pl-2.5 font-mono text-2xs tabular-nums text-text-muted">
              {row.wpm || 0} {t("сл/мин")}
            </span>
          </div>
        ))}

        {/* Итог словами - под полосами. Число собрано в Python (ratio), хвост
            фразы - готовый ключ перевода. */}
        {ratio && ratio !== "-" ? (
          <p className="font-sans text-sm leading-[1.3] text-text-secondary">
            {ratio} {t("быстрее, чем печатать руками")}
          </p>
        ) : null}
      </div>
    </Card>
  );
}
