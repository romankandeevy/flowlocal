// Список страниц окна: порядок в меню, иконка, компонент.
//
// Одно место на всё окно. Страница добавляется сюда - и сразу появляется в
// меню; отдельного списка в app.tsx нет и заводить нельзя, он разъедется.
//
// Порядок тот же, что в QML-версии: он не алфавитный и не случайный - сверху
// то, куда заходят каждый день, снизу то, куда заходят раз в месяц.
//
// **Страница, которую ещё не перенесли, стоит здесь заглушкой.** Не пустым
// местом и не пропуском в меню: человек, открывший программу, должен видеть
// все разделы на своих местах, иначе ему покажется, что половина настроек
// исчезла. Заглушка честно говорит, что раздел пока открывается в старом окне.
import type { ComponentType } from "react";

import { t } from "../i18n";
import type { IconName } from "../ui/icons";
import { Card } from "../ui/card";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";
import { DictationPage } from "./dictation";
import { HistoryPage } from "./history";

interface Page {
  icon: IconName;
  component: ComponentType;
}

/** Заглушка для того, что ещё не переехало. */
function Soon({ name }: { name: string }) {
  return (
    <>
      <Heading level="page">{t(name)}</Heading>
      <Card>
        <SettingRow
          first
          title={t("Этот раздел пока в прежнем окне")}
          subtitle={t(
            "Настройки на месте и работают - переезд идёт по одной странице.",
          )}
        />
      </Card>
    </>
  );
}

function soon(name: string): ComponentType {
  const C = () => <Soon name={name} />;
  C.displayName = `Soon(${name})`;
  return C;
}

export const PAGES = {
  "Главная": { icon: "home", component: soon("Главная") },
  "Диктовка": { icon: "asr", component: DictationPage },
  "Слова": { icon: "dictionary", component: soon("Слова") },
  "История": { icon: "history", component: HistoryPage },
  "Статистика": { icon: "stats", component: soon("Статистика") },
  "Заметки": { icon: "notes", component: soon("Заметки") },
  "Дополнительно": { icon: "extra", component: soon("Дополнительно") },
  "О программе": { icon: "about", component: soon("О программе") },
} satisfies Record<string, Page>;

export type PageKey = keyof typeof PAGES;

/** С чего открывается окно.
 *
 * Отдельной постоянной, а не строкой в app.tsx: там она была бы просто
 * русским текстом среди кода, и её нельзя ни отличить от подписи, ни
 * проверить на совпадение с ключом реестра. Здесь опечатка падает на tsc.
 */
export const DEFAULT_PAGE: PageKey = "Главная";
