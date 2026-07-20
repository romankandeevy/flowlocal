// Выпадающий список. Голова 30 в высоту, радиус 6; меню - радиус 8, строки на
// отступ меньше (8 - 4 = 4). Одинаковый радиус у вложенных углов выглядит
// неправильно даже там, где глаз не объясняет чем.
//
// Что досталось даром против QML. Там список был нарисован из двух Rectangle с
// ListView внутри, и к нему руками написаны: открытие по Space и Enter, ходьба
// стрелками, Esc, отдельное поле `hover` (чтобы стрелки не писали в конфиг на
// каждом шаге), своя `mouseFocus` и FocusRing. Всё это - Radix, плюс то, чего
// в QML не было вовсе:
//
//   * набор букв ведёт к пункту («ги» - к gigaam), а список моделей длинный;
//   * при открытии список прокручивается к выбранному;
//   * щелчок мимо и Esc закрывают, фокус возвращается на голову;
//   * диктор объявляет «список, выбрано …, 3 из 7» - роли combobox/listbox;
//   * меню живёт в портале, а не внутри своей карточки. В QML оно спасалось
//     `z: 100` и всё равно упиралось бы в клип прокрутки страницы.
//
// Значения только строками: в DOM у пункта списка иное и не хранится, а Radix
// на пустую строку ругается отдельно - пустое значение у него означает «ничего
// не выбрано». Если из Python приедет пункт с пустым value, менять надо там.
import * as RadixSelect from "@radix-ui/react-select";

import { cn } from "../cn";
import { Icon } from "../icons";

export type SelectOption = { label: string; value: string };

export function Select({
  options,
  value,
  onChange,
  disabled = false,
  placeholder,
  label,
  className,
}: {
  options: ReadonlyArray<SelectOption>;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Что показать, пока значение не совпало ни с одним пунктом. */
  placeholder?: string;
  /** Имя для экранного диктора. */
  label?: string;
  className?: string;
}) {
  return (
    <RadixSelect.Root value={value} onValueChange={onChange} disabled={disabled}>
      <RadixSelect.Trigger
        aria-label={label}
        className={cn(
          "group inline-flex h-[30px] w-[290px] cursor-pointer items-center gap-2",
          "rounded-sm border border-border bg-fill-subtle pr-3 pl-3",
          "font-sans text-sm text-text",
          "transition-[background-color,border-color,opacity]",
          "duration-[var(--dur-fast)] ease-out",
          "hover:border-border-strong hover:bg-fill",
          "active:bg-fill-strong",
          // Открытое меню помечаем акцентом на рамке: голова и список - одно
          // целое, и рамка говорит, откуда список вырос.
          "data-[state=open]:border-accent",
          "disabled:cursor-default disabled:opacity-40",
          className,
        )}
      >
        {/* Подпись сжимается первой, шеврон не сжимается никогда: имена
            микрофонов в Windows бывают длиннее самого окна. */}
        <span className="min-w-0 flex-1 truncate text-left">
          <RadixSelect.Value placeholder={placeholder} />
        </span>
        <RadixSelect.Icon
          className={cn(
            "shrink-0 text-text-muted transition-[transform,color]",
            "duration-[var(--dur)] ease-out",
            "group-hover:text-text",
            // Шеврон переворачивается на открытом меню: указывает, куда
            // приведёт следующее нажатие, а не куда привело прошлое.
            "group-data-[state=open]:rotate-180",
          )}
        >
          <Icon name="chevron" size={14} />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className={cn(
            "z-50 max-h-[240px] w-[var(--radix-select-trigger-width)]",
            "overflow-hidden rounded-md border border-border bg-paper shadow-card",
            // Кольцо тут гасим, а не рисуем: фокус при открытии Radix уводит
            // внутрь меню, и общее правило обвело бы кольцом всю коробку. Про
            // выбранный пункт говорит подсветка строки, она же и есть фокус.
            "focus:outline-none",
          )}
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value}
                className={cn(
                  "flex h-7 cursor-pointer items-center rounded-xs px-2",
                  "font-sans text-sm text-text-secondary select-none",
                  "transition-colors duration-[var(--dur-fast)] ease-out",
                  // Подсветка одна на мышь и на клавиатуру: два разных признака
                  // «вот эта строка» на одном списке читались бы как две
                  // строки. Radix и держит их одним состоянием - highlighted.
                  "data-[highlighted]:bg-fill data-[highlighted]:outline-none",
                  "data-[state=checked]:text-text",
                  "data-[disabled]:pointer-events-none data-[disabled]:opacity-40",
                )}
              >
                <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
