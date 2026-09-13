// Заголовки и пояснения. Три QML-контрола схлопнуты в один с уровнем:
// PageTitle, SectionTitle и SectionHeader отличались кеглем и цветом, а не
// поведением, и держать под это три файла незачем.
import type { ReactNode } from "react";

import { cn } from "./cn";

type Level = "page" | "section" | "group";

const LEVELS: Record<Level, string> = {
  // Дисплейный кегль по канону Korti (app-shell, h1): 26px, трекинг -.02em.
  // Вес 700, а не канонические 800: Onest в ExtraBold заметно чернее
  // оригинала и на живом экране придавливал страницу.
  //
  // Трекинг задан в em, а не пикселями: -.02em - это приём, а не число. Буквы
  // на крупном кегле расставлены с запасом под мелкий текст, и без сжатия
  // строка выглядит разболтанной. В QML тут дважды наступали на грабли, считая
  // трекинг от токена, - при смене шкалы он молча становился неправдой.
  page: "text-display font-bold tracking-[-0.02em] text-text",
  // Подпись секции над карточкой: капитель, тесный трекинг, тише текста.
  section:
    "text-2xs font-semibold uppercase tracking-[0.6px] text-text-muted",
  group: "text-md font-medium text-text",
};

export function Heading({
  level = "section",
  children,
  className,
}: {
  level?: Level;
  children: ReactNode;
  className?: string;
}) {
  const Tag = level === "page" ? "h1" : level === "section" ? "h2" : "h3";
  // Тег по уровню, а не div со стилями: экранный диктор объявляет заголовок
  // заголовком и умеет прыгать по ним. Ровно того, чего в QML-версии нет
  // вовсе, - там всё это Text.
  return <Tag className={cn("font-sans", LEVELS[level], className)}>{children}</Tag>;
}

/** Пояснение под карточкой. */
export function Note({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "w-full font-sans text-sm leading-[1.3] text-text-muted",
        className,
      )}
    >
      {children}
    </p>
  );
}
