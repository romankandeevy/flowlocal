// Список страниц окна: порядок в меню, иконка, компонент.
//
// Одно место на всё окно. Страница добавляется сюда - и сразу появляется в
// меню; отдельного списка в app.tsx нет и заводить нельзя, он разъедется.
//
// Порядок тот же, что в QML-версии: он не алфавитный и не случайный - сверху
// то, куда заходят каждый день, снизу то, куда заходят раз в месяц.
//
// Заглушка «раздел пока в прежнем окне» здесь была и больше не нужна: все
// восемь страниц переехали. Смысл её был не в вежливости - человек, открывший
// программу на середине переезда, должен видеть все разделы на своих местах,
// иначе ему кажется, что половина настроек исчезла. Понадобится снова - брать
// из истории, а не писать заново.
import type { ComponentType } from "react";

import type { IconName } from "../ui/icons";
import { AboutPage } from "./about";
import { AdvancedPage } from "./advanced";
import { DictationPage } from "./dictation";
import { HistoryPage } from "./history";
import { HomePage } from "./home";
import { NotesPage } from "./notes";
import { StatsPage } from "./stats";
import { WordsPage } from "./words";

interface Page {
  icon: IconName;
  component: ComponentType;
}

export const PAGES = {
  "Главная": { icon: "home", component: HomePage },
  "Диктовка": { icon: "asr", component: DictationPage },
  "Слова": { icon: "dictionary", component: WordsPage },
  "История": { icon: "history", component: HistoryPage },
  "Статистика": { icon: "stats", component: StatsPage },
  "Заметки": { icon: "notes", component: NotesPage },
  "Дополнительно": { icon: "extra", component: AdvancedPage },
  "О программе": { icon: "about", component: AboutPage },
} satisfies Record<string, Page>;

export type PageKey = keyof typeof PAGES;

/** С чего открывается окно.
 *
 * Отдельной постоянной, а не строкой в app.tsx: там она была бы просто
 * русским текстом среди кода, и её нельзя ни отличить от подписи, ни
 * проверить на совпадение с ключом реестра. Здесь опечатка падает на tsc.
 */
export const DEFAULT_PAGE: PageKey = "Главная";
