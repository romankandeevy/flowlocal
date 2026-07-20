// Ползунок: дорожка 5, пройденная часть акцентом, ручка 14 бумажная с линией.
// Значение подписано справа - без него ползунок бесполезен: «где-то посередине»
// это не настройка, человеку нужно видеть, что он выставил.
//
// Что досталось даром против QML. Там написаны `snap`, `set`, разбор
// Left/Right/Up/Down/Home/End, пересчёт координаты мыши в значение с поправкой
// на половину ручки, своя `mouseFocus` и FocusRing. Здесь это Radix, и сверх
// того - PageUp/PageDown, перетаскивание с захватом указателя (палец может
// уехать за пределы дорожки, и значение не потеряется) и роль slider с
// aria-valuenow, то есть диктор наконец называет число.
//
// Кольцо фокуса тут садится на ручку, а не на дорожку, как было в QML. Там
// кольцо рисовали сами и могли посадить куда угодно; здесь оно принадлежит
// тому элементу, который держит фокус, а это ручка. Переносить его на дорожку
// значило бы вернуть своё кольцо - ровно то, от чего переезд избавляет.
import * as RadixSlider from "@radix-ui/react-slider";

import { cn } from "../cn";

export function Slider({
  value,
  onChange,
  onCommit,
  from = 0,
  to = 1,
  step = 0.1,
  suffix = " с",
  trackWidth = 130,
  disabled = false,
  label,
  className,
}: {
  value: number;
  /** Зовётся на каждом шаге, в том числе пока ручку ведут. */
  onChange: (value: number) => void;
  /** Зовётся один раз, когда ручку отпустили. Сюда вешают запись в конфиг. */
  onCommit?: (value: number) => void;
  from?: number;
  to?: number;
  step?: number;
  suffix?: string;
  trackWidth?: number;
  disabled?: boolean;
  /** Имя для экранного диктора. */
  label?: string;
  className?: string;
}) {
  // Запятая, а не точка: это русский интерфейс, и «0.5 с» тут читается
  // машинным. Один знак после запятой - шаг настроек десятые, и второй знак
  // был бы враньём о точности.
  const shown = value.toFixed(1).replace(".", ",") + suffix;

  return (
    <span
      className={cn(
        "group inline-flex h-[22px] items-center gap-3",
        "transition-opacity duration-[var(--dur-fast)] ease-out",
        disabled && "opacity-40",
        className,
      )}
    >
      <RadixSlider.Root
        value={[value]}
        min={from}
        max={to}
        step={step}
        disabled={disabled}
        onValueChange={(next) => {
          const first = next[0];
          if (first !== undefined) onChange(first);
        }}
        onValueCommit={(next) => {
          const first = next[0];
          if (first !== undefined && onCommit) onCommit(first);
        }}
        className="relative flex h-[22px] touch-none items-center select-none"
        style={{ width: trackWidth }}
      >
        <RadixSlider.Track className="relative h-[5px] w-full grow rounded-full bg-fill-strong">
          <RadixSlider.Range className="absolute h-full rounded-full bg-accent" />
        </RadixSlider.Track>
        <RadixSlider.Thumb
          aria-label={label}
          className={cn(
            "block size-[14px] rounded-full border border-border bg-paper",
            "transition-[transform,border-color] duration-[var(--dur-fast)] ease-out",
            // Под пальцем ручка чуть подрастает - тот же жест, что у кнопки
            // «утонуть», но наоборот: кнопку нажимают, а ручку берут.
            "hover:scale-[1.08] hover:border-border-strong",
            "active:scale-[1.15] active:border-border-strong",
            disabled ? "cursor-default" : "cursor-pointer",
          )}
        />
      </RadixSlider.Root>

      {/* Пока ползунок ведут, подпись - главное, на что смотрят: она одна
          говорит, что именно выставлено. На это время поднимаем её в полный
          текст, в покое возвращаем в тихий.

          Моноширинный с табличными цифрами: ширина числа не меняется от
          «0,1» к «1,5», и подпись не дёргается при перетаскивании. Ширина
          задана заодно - иначе на «1,0 с» и «0,5 с» ряд ездил бы целиком. */}
      <span
        className={cn(
          "min-w-[42px] font-mono text-2xs tabular-nums text-text-secondary",
          "transition-colors duration-[var(--dur-fast)] ease-out",
          "group-focus-within:text-text group-active:text-text",
        )}
      >
        {shown}
      </span>
    </span>
  );
}
