// Витрина таблиц, пустых состояний и частей оболочки окна.
//
// Данные выдуманы, но правдоподобны: подстановки такие, какие человек заводит
// первыми, термины - те самые полторы сотни, из-за которых свои три когда-то
// терялись. На пустых списках половину этих контролов проверить нельзя - вся их
// работа как раз в том, чтобы список не был пустым.
//
// Раздел подключается в общую витрину (ui/showcase.tsx) отдельным блоком.
import { useState } from "react";

import { Button } from "../button";
import { Card } from "../card";
import { Heading, Note } from "../text";
import { Backdrop, VersionsDialog, type VersionEntry } from "./dialog";
import { EmptyState } from "./empty-state";
import { HotkeyField } from "./hotkey-field";
import { NavItem, Wordmark } from "./nav";
import { countBlanks, PairTable, type Pair } from "./pair-table";
import {
  countTransformBlanks,
  TransformTable,
  type Transform,
} from "./transform-table";

const PAIRS: Pair[] = [
  { k: "моя почта", v: "roman@example.com" },
  { k: "мой телефон", v: "+7 900 123-45-67" },
  { k: "подпись", v: "С уважением, Роман. {дата}" },
];

// Те самые «системные, для программирования». Показываем шесть - счётчик рядом
// с заголовком врать не должен, поэтому и число в витрине настоящее.
const READY: Pair[] = [
  { k: "джейсон", v: "JSON" },
  { k: "гит хаб", v: "GitHub" },
  { k: "пайтон", v: "Python" },
  { k: "апи", v: "API" },
  { k: "реакт", v: "React" },
  { k: "эс кью эль", v: "SQL" },
];

const TRANSFORMS: Transform[] = [
  { title: "По-деловому", instruction: "Перепиши вежливо и по делу, ничего не выбрасывая" },
  { title: "Для отца", instruction: "Объясни простыми словами, без терминов" },
  { title: "", instruction: "Убери повторы" },
];

const VERSIONS: VersionEntry[] = [
  {
    version: "0.21",
    date: "12.07.2026",
    title: "Пилюля перестала забирать фокус",
    items: [
      "Окно пилюли больше не перехватывает Ctrl+V у активной программы",
      "Волна рисуется на 60 кадрах вместо 30",
      "Починена вставка длинного текста - раньше отказывала молча",
    ],
  },
  {
    version: "0.20",
    date: "28.06.2026",
    title: "Словарь и подстановки",
    items: [
      "Свои слова: фамилии и названия пишутся так, как написали вы",
      "Подстановки: «моя почта» превращается в адрес",
    ],
  },
  {
    version: "0.19",
    date: "14.06.2026",
    title: "Программа просыпается вместе с машиной",
    items: [
      "После сна и ввода PIN сочетание работает сразу",
      "Залипшие клавиши чистятся при пробуждении",
    ],
  },
];

const PAGES = ["Главная", "История", "Статистика", "Заметки"] as const;

export function MiscShowcase() {
  const [pairs, setPairs] = useState(PAIRS);
  const [ready, setReady] = useState(READY);
  const [transforms, setTransforms] = useState(TRANSFORMS);
  const [emptyPairs, setEmptyPairs] = useState<Pair[]>([]);
  const [page, setPage] = useState<string>("Главная");
  const [capturing, setCapturing] = useState<string | null>(null);
  const [hotkeys, setHotkeys] = useState<Record<string, string>>({
    hotkey_hold: "Ctrl + Shift + Space",
    hotkey_toggle: "Ctrl + Alt + D",
    hotkey_notes: "",
  });
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [backdrop, setBackdrop] = useState(false);

  const blanks = countBlanks(pairs);
  const tfBlanks = countTransformBlanks(transforms);

  return (
    <div className="flex flex-col gap-10">
      {backdrop ? <Backdrop /> : null}

      <Section title="Вордмарк и боковое меню">
        <Card>
          <div className="flex flex-col gap-6 p-6">
            <div className="flex items-center gap-8">
              <Wordmark />
              <Wordmark size="lg" />
            </div>
            {/* Пункты в <nav>, а не в голом столбике: это меню окна, и диктор
                должен уметь прыгнуть в него одной командой. */}
            <nav className="flex w-[212px] flex-col gap-1">
              {PAGES.map((name) => (
                <NavItem
                  key={name}
                  label={name}
                  icon={
                    name === "Главная"
                      ? "home"
                      : name === "История"
                        ? "history"
                        : name === "Статистика"
                          ? "stats"
                          : "notes"
                  }
                  active={page === name}
                  onClick={() => setPage(name)}
                />
              ))}
            </nav>
          </div>
        </Card>
        <Note>
          Активный пункт объявляется текущей страницей, а не только красится
          заливкой: в QML-версии на слух он не отличался никак.
        </Note>
      </Section>

      <Section title="Фон окна">
        <Card>
          <div className="flex items-center gap-4 p-6">
            <Button
              label={backdrop ? "Убрать фон" : "Показать фон"}
              onClick={() => setBackdrop(!backdrop)}
            />
            <Note className="flex-1">
              Точки и прожектор ложатся под всё окно целиком, поэтому показать
              их кусочком нельзя - только включить.
            </Note>
          </div>
        </Card>
      </Section>

      <Section title="Пустые состояния">
        <Card>
          <EmptyState
            icon="history"
            title="Здесь появится всё, что вы надиктуете"
            // Плашки клавиш рисует KeyCaps - он живёт отдельным файлом и в эту
            // витрину не входит. Здесь на его месте просто строка, чтобы было
            // видно, куда он встанет.
            combo={
              <span className="font-mono text-2xs text-text-muted">
                Ctrl + Shift + Space
              </span>
            }
            hint="Скажите что-нибудь - каждая фраза ляжет карточкой с кнопкой «Скопировать»."
          />
        </Card>
        <Card>
          <EmptyState
            icon="stats"
            title="Здесь появятся ваши числа"
            hint="Сначала задайте сочетание на странице «Диктовка»."
            alarm
          />
        </Card>
        <Card>
          <EmptyState
            icon="dictionary"
            title="Пока ни одного слова"
            hint="Впишите фамилию, название или термин - по одному на строку. Дальше программа будет писать их так же."
            actionLabel="Вписать слово"
          />
        </Card>
      </Section>

      <Section title="Сочетания клавиш">
        <Card>
          <div className="flex flex-col gap-3 p-6">
            <HotkeyField
              field="hotkey_hold"
              value={hotkeys["hotkey_hold"] ?? ""}
              capturing={capturing === "hotkey_hold"}
              onStartCapture={setCapturing}
              onCancelCapture={() => setCapturing(null)}
            />
            <HotkeyField
              field="hotkey_toggle"
              value={hotkeys["hotkey_toggle"] ?? ""}
              capturing={capturing === "hotkey_toggle"}
              allowClear
              onStartCapture={setCapturing}
              onCancelCapture={() => setCapturing(null)}
              onClear={(f) => setHotkeys({ ...hotkeys, [f]: "" })}
            />
            <HotkeyField
              field="hotkey_notes"
              value={hotkeys["hotkey_notes"] ?? ""}
              allowClear
              disabled
            />
          </div>
        </Card>
        <Note>
          Нажатие начинает захват, но ловит сочетание Python: браузеру Win не
          отдают вовсе. Здесь видно только «жду нажатия» - выйти из него можно
          повторным нажатием или Esc.
        </Note>
      </Section>

      <Section title="Подстановки">
        <PairTable
          rows={pairs}
          ready={ready}
          onChange={(next) => {
            setPairs(next.rows);
            setReady(next.ready);
          }}
          caption="Подстановки"
          leftHeader="Что говорю"
          rightHeader="Что вставится"
          leftPlaceholder="моя почта"
          rightPlaceholder="roman@example.com"
          readyTitle="Термины для программирования"
          readyHint="Их добавила программа. Ваши - выше"
        />
        <Note>
          В правой части работают: {"{дата}"}, {"{дата-словами}"}, {"{время}"},{" "}
          {"{день-недели}"}
        </Note>
        {blanks > 0 ? (
          <Note>Незаполненных строк: {blanks} - они не сохранятся.</Note>
        ) : null}
      </Section>

      <Section title="Подстановки: пусто, но с приглашением">
        <PairTable
          rows={emptyPairs}
          onChange={(next) => setEmptyPairs(next.rows)}
          caption="Подстановки"
          leftHeader="Что говорю"
          rightHeader="Что вставится"
          leftPlaceholder="моя почта"
          rightPlaceholder="roman@example.com"
          showBlankRow
        />
        <Note>
          Живая строка объясняет устройство сама, без единого слова. В данных её
          нет, пока в неё не начали печатать.
        </Note>
      </Section>

      <Section title="Свои преобразования">
        <TransformTable rows={transforms} onChange={setTransforms} />
        {tfBlanks > 0 ? (
          <Note>Незаполненных строк: {tfBlanks} - они не сохранятся.</Note>
        ) : null}
        <TransformTable rows={[]} onChange={() => {}} />
      </Section>

      <Section title="Прежние версии">
        <Card>
          <div className="flex items-center gap-4 p-6">
            <Button
              label="Показать прежние версии"
              onClick={() => setVersionsOpen(true)}
            />
            <Note className="flex-1">
              Esc, клик мимо и «Закрыть» делают одно и то же, а после закрытия
              фокус возвращается на эту кнопку.
            </Note>
          </div>
        </Card>
        <VersionsDialog
          open={versionsOpen}
          onClose={() => setVersionsOpen(false)}
          title="Прежние версии"
          versions={VERSIONS}
        />
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <Heading>{title}</Heading>
      {children}
    </section>
  );
}
