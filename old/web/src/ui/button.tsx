// Кнопка. Три вида: primary, secondary, danger.
//
// Ступени отклика одни и те же у всех: покой -> ховер -> нажатие. В QML
// нажатие поначалу цвета не меняло, и весь отклик держался на сдвиге в один
// пиксель - на тёмной теме его было не разглядеть. Сдвиг оставлен, но не один.
//
// Что здесь досталось даром против QML. Там кнопка - это Item плюс MouseArea
// плюс ручной разбор Space и Enter плюс FocusRing плюс своя `mouseFocus`,
// потому что activeFocus загорается и от щелчка мышью. Здесь всё это - <button>
// и :focus-visible: браузер сам знает, что фокус от мыши подсвечивать не надо,
// а Space и Enter нажимают кнопку без единой строки. Ради этого переезд и
// затевался.
import type { ReactNode } from "react";

import { cn } from "./cn";

type Kind = "primary" | "secondary" | "danger";

const KINDS: Record<Kind, string> = {
  primary: cn(
    "bg-primary text-primary-fg border-transparent",
    "hover:bg-[color-mix(in_srgb,var(--color-ink)_84%,transparent)]",
    "active:bg-[color-mix(in_srgb,var(--color-ink)_72%,transparent)]",
  ),
  secondary: cn(
    "bg-fill text-text border-border",
    "hover:bg-fill-strong hover:border-border-strong",
    "active:bg-border-strong",
  ),
  danger: cn(
    "text-danger",
    "bg-[color-mix(in_srgb,var(--color-danger)_6%,transparent)]",
    "border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)]",
    "hover:bg-[color-mix(in_srgb,var(--color-danger)_12%,transparent)]",
    "active:bg-[color-mix(in_srgb,var(--color-danger)_18%,transparent)]",
  ),
};

export function Button({
  label,
  kind = "secondary",
  disabled = false,
  onClick,
  className,
  children,
}: {
  label?: string;
  kind?: Kind;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-[30px] min-w-[72px] cursor-pointer items-center",
        "justify-center rounded-sm border px-3 font-sans text-sm font-semibold",
        "transition-[background-color,border-color,opacity]",
        "duration-[var(--dur-fast)] ease-out",
        // Нажатие - на пиксель вниз. Не тень и не масштаб: система разрешает
        // ровно этот жест.
        "active:translate-y-px",
        // Выключенная гасится целиком, а не перекрашивается по частям: одно
        // правило вместо ветвления в каждом из трёх видов. Курсор обычный -
        // палец обещает нажатие, которого не будет.
        "disabled:cursor-default disabled:opacity-40",
        KINDS[kind],
        className,
      )}
    >
      {children ?? label}
    </button>
  );
}
