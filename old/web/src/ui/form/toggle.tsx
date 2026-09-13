// Переключатель. 38x22, ручка 16, ход 16 - размеры сверены по Korti Switch,
// а не подобраны на глаз.
//
// Включённый - это ЧЕРНИЛА, а не акцент: акцент в системе выделяет особое, а
// не «включено». Отсюда --color-primary у дорожки: в обеих темах это и есть
// ink, поэтому одно правило вместо двух.
//
// Что досталось даром против QML. Там переключатель - это Item, ручной разбор
// Space и Enter, своя `mouseFocus`, свой FocusRing и никакого голоса у
// экранного диктора: для него это был безымянный прямоугольник. Здесь Radix
// рисует <button role="switch" aria-checked>, и диктор наконец называет
// переключатель переключателем - ровно тот пункт ручной проверки, который в
// плане записан как «этого сейчас нет вовсе».
import * as Switch from "@radix-ui/react-switch";
import type { ReactNode } from "react";

import { cn } from "../cn";
import { SettingRow } from "../setting-row";

export function Toggle({
  checked,
  onChange,
  disabled = false,
  label,
  className,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Имя для экранного диктора. Без него он читает только «вкл/выкл». */
  label?: string;
  className?: string;
}) {
  return (
    <Switch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label={label}
      className={cn(
        "group relative inline-flex h-[22px] w-[38px] shrink-0 cursor-pointer",
        "items-center rounded-full border border-border bg-fill-strong",
        "transition-[background-color,border-color,opacity]",
        // Ход - 120 мс, самый быстрый токен, а не общие 180. Тумблер не
        // показывает переход, он отвечает на палец: на 180 щелчок успевал
        // прочитаться как задержка.
        "duration-[var(--dur-fast)] ease-out",
        // Ховер по правилу системы: заливка на ступень выше, без смены цвета.
        // Только у выключенного - у включённого дорожка уже сплошная.
        "data-[state=unchecked]:hover:bg-[color-mix(in_srgb,var(--color-ink)_20%,transparent)]",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        "disabled:cursor-default disabled:opacity-40",
        className,
      )}
    >
      <Switch.Thumb
        className={cn(
          "pointer-events-none block size-4 rounded-full bg-bg",
          // Ход 16: от 3 до 19 по внешнему краю, минус пиксель рамки - отсюда
          // 2 и 18. Едет transform'ом, а не left: transform не трогает
          // раскладку и считается на композиторе, то есть ручка не заставляет
          // браузер пересчитывать строку настройки на каждом кадре.
          "translate-x-[2px] data-[state=checked]:translate-x-[18px]",
          "transition-transform duration-[var(--dur-fast)] ease-out",
          // Нажатие: ручка чуть тонет. Масштаб, а не сдвиг, - сдвиг тут
          // неотличим от хода, ради которого переключатель и существует.
          "group-active:scale-[0.88]",
        )}
      />
    </Switch.Root>
  );
}

/**
 * Строка настройки с переключателем. Сахар: таких строк в настройках восемь, и
 * каждый раз писать Toggle внутри SettingRow - шум.
 *
 * В QML сюда же был вшит ключ конфига (`path` плюс `B.get`/`B.set`). Здесь
 * строка остаётся управляемой: значение и обработчик приходят снаружи. Ключ -
 * дело моста, а мост даёт свой хук на настройку; вшить его сюда значит
 * запретить эту же строку там, где значение считается, а не лежит в конфиге.
 */
export function ToggleRow({
  title,
  subtitle,
  more,
  icon,
  first = false,
  checked,
  onChange,
  disabled = false,
}: {
  title: string;
  subtitle?: ReactNode;
  more?: ReactNode;
  icon?: ReactNode;
  first?: boolean;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <SettingRow title={title} subtitle={subtitle} more={more} icon={icon} first={first}>
      {/* Заголовок ряда отдаём переключателю именем: диктор читает «Не терять
          первое слово, переключатель, включено», а не «переключатель, включено»
          посреди списка из восьми одинаковых. */}
      <Toggle checked={checked} onChange={onChange} disabled={disabled} label={title} />
    </SettingRow>
  );
}
