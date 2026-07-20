// Окно настроек: боковое меню слева, страница справа, плашка сообщений снизу.
//
// Роутер свой на useState, а не библиотека. Восьми страницам в одном окне
// маршрутизация не нужна вовсе: URL никто не видит, назад-вперёд браузерных
// кнопок нет, ссылок между страницами тоже. React Router здесь - это 10 КБ и
// абстракция ради одного switch.
//
// **Страницы переезжают по одной, и обе версии живут рядом.** Настройка
// `ui.web_pages` перечисляет то, что уже переехало; всё остальное окно
// показывает старой QML-версией. Так на каждом шаге есть рабочая программа, а
// не полусобранная.
import { useEffect, useState } from "react";

import { on } from "./bridge/api";
import { peek } from "./bridge/client";
import { t } from "./i18n";
import { DEFAULT_PAGE, PAGES, type PageKey } from "./pages/registry";
import { cn } from "./ui/cn";
import { Icon } from "./ui/icons";
import { LayoutModeProvider, type LayoutMode } from "./ui/layout-mode";

/** Сообщение внизу окна: «сохранено», «не удалось скачать». */
interface Flash {
  text: string;
  kind: string;
}

export function App() {
  const [page, setPage] = useState<PageKey>(DEFAULT_PAGE);
  const [flash, setFlash] = useState<Flash | null>(null);
  const layout = (peek("layout") as LayoutMode) ?? "cards";

  // Плашка приходит сигналом Backend - тем же, что и в QML-версии. Гасим её
  // сами через три секунды: у сигнала нет пары «погасить», и раньше это делал
  // таймер в окне.
  useEffect(() => {
    const off = on("flashed", (text, kind) => {
      setFlash({ text: String(text), kind: String(kind) });
    });
    return off;
  }, []);

  useEffect(() => {
    if (!flash) return;
    const id = window.setTimeout(() => setFlash(null), 3000);
    return () => window.clearTimeout(id);
  }, [flash]);

  const Current = PAGES[page].component;

  return (
    <LayoutModeProvider mode={layout}>
      <div className="flex h-screen bg-bg text-text">
        <Nav page={page} onPick={setPage} />

        {/* Прокручивается только страница, а не окно: меню слева должно
            оставаться на месте, иначе на длинной «Диктовке» до него не
            добраться, не промотав всё обратно. */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-[640px] flex-col gap-8 px-8 py-8">
            <Current />
          </div>
        </main>

        {flash ? (
          <div
            role="status"
            className={cn(
              "fixed bottom-6 left-1/2 -translate-x-1/2 rounded-md px-4 py-2",
              "font-sans text-sm shadow-card",
              flash.kind === "danger"
                ? "bg-danger text-text-inverse"
                : "bg-primary text-primary-fg",
            )}
          >
            {flash.text}
          </div>
        ) : null}
      </div>
    </LayoutModeProvider>
  );
}

function Nav({
  page,
  onPick,
}: {
  page: PageKey;
  onPick: (p: PageKey) => void;
}) {
  const keys = Object.keys(PAGES) as PageKey[];
  return (
    // nav с aria-label, а не голый div: диктор объявляет область навигации и
    // умеет прыгать к ней. В QML-версии это Column, и он для диктора немой.
    <nav
      aria-label={t("Разделы настроек")}
      className="w-[210px] shrink-0 border-r border-border bg-surface-sunken px-3 py-4"
    >
      <ul className="flex flex-col gap-0.5">
        {keys.map((key) => (
          <li key={key}>
            <button
              type="button"
              // aria-current, а не только краска: «где я сейчас» диктор иначе
              // не сообщает вовсе.
              aria-current={key === page ? "page" : undefined}
              onClick={() => onPick(key)}
              className={cn(
                "flex w-full cursor-pointer items-center gap-2.5 rounded-md",
                "px-3 py-2 text-left font-sans text-sm",
                "transition-colors duration-[var(--dur-fast)]",
                key === page
                  ? "bg-fill-strong text-text"
                  : "text-text-secondary hover:bg-fill hover:text-text",
              )}
            >
              <Icon name={PAGES[key].icon} size={17} aria-hidden="true" />
              {t(key)}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
