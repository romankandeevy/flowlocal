// Строка статистики: число справа, крупно.
//
// Кегль 20, а не дисплейный 26. Дисплейный в Korti - для витрины метрик, где
// число одно и оно главное на экране. Здесь пять строк подряд в столбик, и в
// дисплейном каждая читалась заголовком: страница «Статистика» превращалась в
// пять заголовков без текста. Число всё равно самое заметное в строке - оно
// справа, полужирное и одно.
//
// Цифры табличные - соседние строки не пляшут по ширине. В QML ради этого
// собирались перейти на моноширинный (так и написано в шапке контрола, хотя
// код остался на Onest), здесь хватает font-variant-numeric: подпись остаётся
// тем же шрифтом, что и вся страница, а цифры выстраиваются в колонку.
import type { ReactNode } from "react";

import { SettingRow } from "../setting-row";

export function StatRow({
  title,
  subtitle,
  more,
  icon,
  first = false,
  value,
}: {
  title: string;
  subtitle?: ReactNode;
  more?: ReactNode;
  icon?: ReactNode;
  first?: boolean;
  /** Пусто - строка только рассказывает: так стоит «Ваша манера». */
  value: string;
}) {
  return (
    <SettingRow title={title} subtitle={subtitle} more={more} icon={icon} first={first}>
      {value ? (
        <span className="font-sans text-xl font-semibold tracking-[-0.02em] tabular-nums text-text">
          {value}
        </span>
      ) : null}
    </SettingRow>
  );
}
