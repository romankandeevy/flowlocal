// Карточка: бумага, волосяная линия, радиус 12. Канон Korti, `.ins-card`.
//
// В QML корнем стоит Item, а не Rectangle, потому что тень рисует MultiEffect,
// которому нужна сама карточка источником, - эффект внутри своего источника
// даёт петлю в графе отрисовки. В вебе этой беды нет: box-shadow рисуется
// вместе с элементом, и обёртка не нужна. Один div вместо трёх.
//
// Тень включена по умолчанию, но выключается там, где содержимое ДВИЖЕТСЯ.
// Правило не вкусовое, а про цену кадра: в QML размытие пересчитывалось по
// всему прямоугольнику на каждом изменении источника, и у метрики с добегающим
// числом это выходило на каждый кадр. В браузере box-shadow дешевле, но
// поднимает слой на композитор, и на движущемся содержимом это те же лишние
// перерисовки. Правило сохраняем - оно про то же самое.
import type { ReactNode } from "react";

import { cn } from "./cn";
import { useLayoutMode } from "./layout-mode";

export function Card({
  children,
  shadow = true,
  className,
}: {
  children: ReactNode;
  /** Выключать там, где внутри карточки что-то движется. */
  shadow?: boolean;
  className?: string;
}) {
  const lines = useLayoutMode() === "lines";
  return (
    <div
      className={cn(
        "w-full",
        // «Линии» - то же содержимое без коробки: ни рамки, ни фона, ни тени.
        // Строки разделяются линиями сами, это умеет SettingRow.
        lines
          ? "bg-transparent"
          : cn(
              "bg-paper rounded-lg border border-border",
              shadow && "shadow-card",
            ),
        className,
      )}
    >
      {children}
    </div>
  );
}
