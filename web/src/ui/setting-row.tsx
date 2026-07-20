// Строка настройки: «иконка - название - контрол» сверху, пояснение снизу и
// необязательное раскрытие «подробнее» под ним. Самый частый контрол в окне -
// 54 постановки из 322.
//
// **Почему подпись идёт ПОД контролом, а не слева от него.** Раньше заголовок
// и подпись стояли одной колонкой слева, а контрол забирал правый край - как в
// PowerToys. При ширине колонки 640 так больше не выходит: на подпись остаётся
// 220-300 px, а утверждённые тексты - до 60 знаков, это 400-440 px. Тринадцать
// подписей из сорока переносились на вторую строку, и критерий «ни одной
// видимой строки длиннее одной» ломался ровно там, где его и ставили. Выбор
// был между «резать утверждённые тексты» и «дать подписи всю ширину ряда» -
// взяли второе: план прямо запрещает резать объяснения.
//
// Разделитель - по краю содержимого, а не встык к рамке: у карточки скруглены
// углы, и линия во всю ширину упиралась бы в дугу.
//
// Раскрытие сделано на <details>, а не на своём состоянии с анимацией высоты.
// Причина не в экономии: <details> сам объявляется диктору раскрывающимся и
// сам работает с клавиатуры. В QML под это написано двадцать строк - ручной
// разбор Space и Enter, своя `mouseFocus`, свой FocusRing, - и диктор всё
// равно не знает, что это раскрытие. Плата - высота меняется без плавности;
// interpolate-size пока не везде, а подделывать раскрытие ради анимации
// значит вернуть те двадцать строк.
import { type ReactNode, useId } from "react";

import { cn } from "./cn";

export function SettingRow({
  title,
  subtitle,
  more,
  icon,
  first = false,
  moreMono = false,
  children,
}: {
  title?: string;
  subtitle?: ReactNode;
  /** Длинное объяснение под шевроном. Пусто - шеврона нет вовсе. */
  more?: ReactNode;
  /** Иконка слева. Пусто - текст начинается от края карточки. */
  icon?: ReactNode;
  /** Первая строка карточки - без верхнего разделителя. */
  first?: boolean;
  /** Моноширинный шрифт в раскрытии: послабление для служебной сводки. */
  moreMono?: boolean;
  /** Сам контрол: переключатель, кнопка, поле. */
  children?: ReactNode;
}) {
  const id = useId();
  // Иконка 20 плюс 12 воздуха. Текст раскрытия выравниваем по той же линии,
  // что и подпись, - иначе объяснение выглядит принадлежащим не этому ряду.
  const textLeft = icon ? "pl-14" : "pl-6";

  return (
    <div className={cn("w-full", !first && "border-t border-border")}>
      <div className="flex gap-3 px-6 py-4">
        {icon ? (
          <div className="mt-px shrink-0 text-text-secondary" aria-hidden="true">
            {icon}
          </div>
        ) : null}

        <div className="min-w-0 flex-1">
          <div className="flex min-h-[22px] items-center gap-4">
            {title ? (
              <label
                htmlFor={id}
                className="min-w-0 flex-1 truncate font-sans text-md text-text"
              >
                {title}
              </label>
            ) : (
              <div className="flex-1" />
            )}
            {children ? (
              <div className="shrink-0" id={id}>
                {children}
              </div>
            ) : null}
          </div>

          {subtitle ? (
            <p className="mt-1 font-sans text-sm leading-[1.25] text-text-muted">
              {subtitle}
            </p>
          ) : null}
        </div>
      </div>

      {more ? (
        <details className="group px-6 pb-4">
          <summary
            className={cn(
              "-mt-2 ml-auto inline-flex w-fit cursor-pointer list-none items-center",
              "gap-1 rounded-sm px-1.5 py-0.5 font-sans text-2xs font-medium",
              "text-text-muted transition-colors duration-[var(--dur-fast)]",
              "hover:bg-fill hover:text-text",
              "[&::-webkit-details-marker]:hidden",
            )}
          >
            подробнее
            <svg
              viewBox="0 0 24 24"
              width="13"
              height="13"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              className="transition-transform duration-[var(--dur)] ease-out group-open:rotate-180"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </summary>
          <div
            className={cn(
              textLeft,
              "pt-2 text-sm leading-[1.45] text-text-muted",
              moreMono ? "font-mono" : "font-sans",
            )}
          >
            {more}
          </div>
        </details>
      ) : null}
    </div>
  );
}
