// Дуга серии: «дней подряд» кольцом, а не голым числом. Заполнение дуги - доля
// текущей серии от рекордной (best): полное кольцо значит «вы на своём
// рекорде». Рекорд - честное число из истории (stats._best_streak), а не
// выдуманная цель вроде «до семи»: дуга не должна врать, к чему человек идёт.
//
// Рисуем одним <circle> с пунктиром в обводке, а не дугой на canvas, как было
// в QML. Причина не в экономии строк: strokeDashoffset - обычное свойство CSS,
// и заполнение едет переходом браузера, без единого кадра на нашей стороне.
// Canvas в QML приходилось перерисовывать самим и по чужому сигналу - там даже
// смена темы требовала явного requestPaint, иначе кольцо оставалось в старых
// красках.
//
// Стоит в ряду метрик «Статистики» и подогнан к ним по высоте, чтобы сетка из
// трёх оставалась ровной. Тени нет: внутри движется дуга - см. card.tsx.

import { Card } from "../card";
import { cn } from "../cn";
import { Icon } from "../icons";
import { useLayoutMode } from "../layout-mode";
import { useAfterPaint, useCountUp } from "./metric";

export interface StreakRingProps {
  /** Текущая серия, дней. */
  value: number;
  /** Рекорд серии - потолок дуги. */
  best: number;
  /** Подпись рядом с числом: «дней подряд». */
  label: string;
  /** Строка рекорда под подписью: «рекорд 7». Пусто - строки нет. */
  record?: string;
  /**
   * Дуга умеет раскрываться в календарь по дням. Сам календарь рисует не она:
   * метрика в ряду из трёх не может развернуться на всю ширину страницы, не
   * сломав сетку. Поэтому здесь только нажатие и шеврон, а показывает календарь
   * страница.
   *
   * Выключено по умолчанию: без обработчика курсор-рука и шеврон обещали бы то,
   * чего не будет.
   */
  expandable?: boolean;
  open?: boolean;
  onActivate?: () => void;
}

// Кольцо 56 при обводке 5: радиус считаем по средней линии штриха, иначе он
// вылезет за viewBox ровно на половину своей толщины.
const SIZE = 56;
const STROKE = 5;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;

export function StreakRing({
  value,
  best,
  label,
  record = "",
  expandable = false,
  open = false,
  onActivate,
}: StreakRingProps) {
  const lines = useLayoutMode() === "lines";
  const grown = useAfterPaint();
  const shown = useCountUp(value);

  // best бывает нулём только при пустой истории, а там страница показывает
  // пустое состояние, не эту дугу, - но делим осторожно.
  const target = best > 0 ? Math.min(1, value / best) : 0;
  const filled = grown ? target : 0;

  const body = (
    <div className="flex h-[82px] w-full items-center gap-3 px-4">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        {/* -90° - чтобы дуга шла от 12 часов по часовой, как её читают. */}
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="-rotate-90"
          aria-hidden="true"
          focusable="false"
        >
          {/* Дорожка - полное кольцо тихой заливкой чернил. */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={R}
            fill="none"
            strokeWidth={STROKE}
            stroke="color-mix(in srgb, var(--color-ink) 10%, transparent)"
          />
          {/* Заполнение - акцентом: серия и есть то самое «особенное», ради
              чего синий в системе заведён. Сегодняшний столбик недельного
              графика тоже акцентный, и это не спор - там один день, тут итог. */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={R}
            fill="none"
            strokeWidth={STROKE}
            strokeLinecap="round"
            stroke="var(--color-accent)"
            strokeDasharray={C}
            strokeDashoffset={C * (1 - filled)}
            className="transition-[stroke-dashoffset] duration-[var(--dur-slow)] ease-out"
          />
        </svg>
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center",
            "font-sans text-xl font-bold tracking-[-0.03em] tabular-nums text-text",
          )}
        >
          {Math.round(shown)}
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-0.5 text-left">
        <span className="font-mono text-2xs text-text-muted">{label}</span>
        {record ? (
          <span className="font-sans text-2xs text-text-faint">{record}</span>
        ) : null}
        {/* Что случится по нажатию - словом, а не одним шевроном. Программу
            ставят людям, которые просто пишут письма: значок им ещё надо
            узнать, а слово они прочитают. Тот же довод, что у «подробнее». */}
        {expandable ? (
          <span className="font-sans text-2xs font-medium text-text-muted transition-colors duration-[var(--dur-fast)] group-hover:text-text">
            {open ? "свернуть" : "по дням"}
          </span>
        ) : null}
      </div>

      {expandable ? (
        <Icon
          name="chevron"
          size={14}
          // Мелкая иконка требует штриха потолще - как в строке настройки.
          strokeWidth={2.4}
          className={cn(
            "ml-auto shrink-0 text-text-muted transition-transform duration-[var(--dur)] ease-out",
            "group-hover:text-text",
            open && "rotate-180",
          )}
        />
      ) : null}
    </div>
  );

  return (
    <Card shadow={false}>
      {expandable ? (
        // Кнопка, а не Item с ручным разбором Space и Enter, своей mouseFocus и
        // своим FocusRing, как в QML: календарь за дугой - единственная дверь к
        // виду по дням, и обходить её табом стороной нельзя. Здесь это даёт
        // сам <button>, включая то, что фокус от щелчка мышью не подсвечивается.
        <button
          type="button"
          onClick={onActivate}
          className={cn(
            "group block w-full cursor-pointer text-left",
            "transition-colors duration-[var(--dur-fast)]",
            "hover:bg-fill active:bg-fill-strong",
            // Радиус берём у карточки; в раскладке «линии» коробки нет, и
            // скругления тоже - подсветка иначе торчала бы дугой из прямого
            // ряда.
            lines ? "rounded-none" : "rounded-lg",
          )}
        >
          {body}
        </button>
      ) : (
        body
      )}
    </Card>
  );
}
