// Страница «Заметки»: список слева-сверху, редактор одной заметки - второй вид
// той же страницы. Диктуют В неё, как диктовали в прежнее отдельное окно.
//
// Ключей конфига у страницы нет, поэтому сверка config.json на ней не ловит
// ничего. Всё держится на втором критерии фазы 4 - семь вызовов Backend
// (notesList, noteText, saveNote, newNote, deleteNote, tidyNote, copyText)
// должны делать то же, что в QML-версии. Каждый ниже помечен.
//
// Данные и уборка - в Python, тот же notes.py, что питал прежнее окно. Здесь
// только два вида и переключение между ними.
//
// Чего тут нет и почему. В QML у страницы была функция enter(mode), которой
// трей и хоткей открывали сразу редактор («прошлой» или «новой» заметки по
// настройке notes_open). Дотянуться до неё со страницы нечем: сигнала на это
// у Backend нет, а зовётся она из окна. Пункт для того, кто будет сшивать
// оболочку, - страница открывается списком.
import { useEffect, useRef, useState } from "react";

import {
  copyText,
  deleteNote,
  newNote,
  noteText,
  notesList,
  on,
  saveNote,
  tidyNote,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { FlowInput } from "../ui/form/input";
import { Icon } from "../ui/icons";
import { EmptyState } from "../ui/misc/empty-state";
import { Heading } from "../ui/text";

interface Note {
  id: string;
  title: string;
  preview: string;
  when: string;
}

/** Сколько ждём паузу в наборе, прежде чем писать файл. */
const AUTOSAVE_MS = 700;

export function NotesPage() {
  const [view, setView] = useState<"list" | "editor">("list");
  const [rows, setRows] = useState<Note[]>([]);
  const [current, setCurrent] = useState("");
  const [query, setQuery] = useState("");
  const [text, setText] = useState("");
  /** Идёт «привести в порядок». */
  const [busy, setBusy] = useState(false);
  /** Жалоба редактора: почему причесать не вышло. Пусто - жалобы нет. */
  const [note, setNote] = useState("");
  const editor = useRef<HTMLTextAreaElement>(null);

  // ВЫЗОВ B.notesList(запрос) - список заметок, свежие первыми.
  //
  // Ищем в Python на каждую букву, а не фильтруем полученный список, как это
  // делает «История». Разница не в небрежности: история приезжает целиком
  // одним вызовом, а заметки лежат отдельными файлами, и поиск идёт по их
  // тексту, которого в списке нет - там только заголовок и первая строка.
  async function reload(q = query) {
    setRows((await notesList(q)) as Note[]);
  }

  useEffect(() => {
    void reload("");
  }, []);

  // Причёсанный текст приходит из Python сигналом: считает его рабочий поток,
  // а трогать поле можно только отсюда.
  useEffect(() => {
    return on("noteTidied", (id, tidied, complaint) => {
      setBusy(false);
      if (complaint !== "") {
        // Жалоба - только той заметке, которую сейчас смотрят: ответ мог
        // прийти после ухода на другую.
        if (id === current) setNote(String(complaint));
        return;
      }
      if (id === current) {
        setNote("");
        setText(String(tidied));
      }
      void reload(); // превью причёсанного в списке
    });
  }, [current, query]);

  // Сохраняем не на каждую букву, а через паузу после последней: заметку пишут
  // диктовкой, кусками по десятку слов, и писать файл на каждое нажатие
  // незачем.
  //
  // ВЫЗОВ B.saveNote(id, текст) - автосейв.
  useEffect(() => {
    if (!current) return;
    const id = window.setTimeout(() => void saveNote(current, text), AUTOSAVE_MS);
    return () => window.clearTimeout(id);
  }, [current, text]);

  // Поле под фокус, как только показали редактор: диктовка вставляется в
  // активное поле, и без фокуса надиктованному некуда лечь.
  useEffect(() => {
    if (view === "editor") editor.current?.focus();
  }, [view]);

  /** Новая заметка и сразу в редактор. */
  async function addNote() {
    // ВЫЗОВ B.newNote() - завести пустую, вернуть идентификатор.
    const id = await newNote();
    if (!id) return;
    setCurrent(id);
    setNote("");
    setText("");
    void reload();
    setView("editor");
  }

  async function openNote(id: string) {
    // ВЫЗОВ B.noteText(id) - текст заметки целиком.
    //
    // Текст берём ДО того, как переставить current, и меняем оба разом. Иначе
    // между двумя обновлениями остаётся кадр, где у нового идентификатора
    // лежит текст прошлой заметки, - и автосейв, сработай он в этот миг,
    // записал бы чужие слова поверх открытой.
    const body = await noteText(id);
    setCurrent(id);
    setNote("");
    setText(body);
    setView("editor");
  }

  /** К списку без сохранения - заметку только что удалили. */
  function toList() {
    setNote("");
    void reload();
    setView("list");
  }

  /**
   * К списку с сохранением - обычный «Назад».
   *
   * Сохраняем явно, а не полагаемся на автосейв: тот ждёт паузу в 700 мс, а
   * уйти можно раньше - тогда последние слова не попали бы ни в превью списка,
   * ни на диск.
   */
  function backToList() {
    if (current) void saveNote(current, text);
    toList();
  }

  async function removeNote(id: string) {
    // ВЫЗОВ B.deleteNote(id).
    await deleteNote(id);
    if (current === id) setCurrent("");
    void reload();
  }

  return (
    <>
      <Heading level="page">{t("Заметки")}</Heading>

      {view === "list" ? (
        <>
          {/* Заголовок с кнопкой справа - тот же приём, что у «Подстановок» на
              «Словах»: кнопка живёт рядом с заголовком, а не в карточке, где
              налезала бы на содержимое строк. */}
          <div className="flex items-center justify-between gap-4">
            <Heading level="section">{t("Недавние")}</Heading>
            <Button
              kind="primary"
              label={t("Добавить")}
              onClick={() => void addNote()}
            />
          </div>

          <FlowInput
            value={query}
            onChange={(v) => {
              setQuery(v);
              void reload(v);
            }}
            label={t("Найти в заметках…")}
            placeholder={t("Найти в заметках…")}
            className="w-full"
          />

          {rows.length === 0 ? (
            // Пусто - зовём начать, тем же EmptyState, что и другие пустые
            // страницы: одно устройство пустоты на всю программу.
            <Card>
              <EmptyState
                icon="notes"
                title={t("Заметок пока нет")}
                hint={t("Нажмите «Добавить» и диктуйте прямо сюда.")}
              />
            </Card>
          ) : (
            // list, а не набор карточек: диктор объявляет «список, 12
            // элементов» и умеет по нему прыгать. В QML это Repeater, и для
            // диктора он немой.
            <ul className="flex flex-col gap-3">
              {rows.map((r) => (
                <li key={r.id}>
                  {/* Тень выключена: карточек в списке бывают десятки, и каждая
                      подняла бы свой слой на композитор. */}
                  <Card shadow={false}>
                    {/* Открыть и удалить - два соседних <button>, а не корзина
                        поверх нажимаемой карточки, как в QML. Кнопку в кнопку
                        вкладывать нельзя, да и диктору так честнее: он читает
                        два разных действия вместо одного с ловушкой внутри. */}
                    <div className="flex items-stretch">
                      <button
                        type="button"
                        onClick={() => void openNote(r.id)}
                        className="flex min-w-0 flex-1 cursor-pointer flex-col gap-1.5 rounded-lg px-5 py-3.5 text-left transition-colors duration-[var(--dur-fast)] hover:bg-fill"
                      >
                        <span className="truncate font-sans text-md font-semibold text-text">
                          {r.title}
                        </span>
                        {/* Превью прячем, когда оно повторяет заголовок: у
                            короткой заметки первая строка и есть заголовок. */}
                        {r.preview && r.preview !== r.title ? (
                          <span className="truncate font-sans text-sm text-text-muted">
                            {r.preview}
                          </span>
                        ) : null}
                        {r.when ? (
                          <span className="font-mono text-2xs text-text-muted">
                            {r.when}
                          </span>
                        ) : null}
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeNote(r.id)}
                        className="m-2 flex size-[34px] shrink-0 cursor-pointer items-center justify-center self-center rounded-sm text-text-muted transition-colors duration-[var(--dur-fast)] hover:bg-fill hover:text-danger"
                      >
                        <Icon name="trash" size={18} />
                        {/* Пять корзин подряд на слух неразличимы, поэтому к
                            действию добавлена сама заметка. Видно это только
                            диктору: глазами строку и так видно. */}
                        <span className="sr-only">
                          {t("Удалить")}: {r.title}
                        </span>
                      </button>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <div>
            <Button label={t("Назад к списку")} onClick={backToList} />
          </div>

          {/* Тень выключена: внутри поле, по которому едет курсор и растёт
              текст. */}
          <Card shadow={false}>
            <textarea
              ref={editor}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("Диктуйте или пишите. Сохраняется само.")}
              aria-label={t("Текст заметки")}
              // resize-none: тянуть угол мышью в своём окне незачем, высота
              // задана раскладкой. Прокрутка своя - текст прибывает кусками, и
              // браузер сам держит курсор в поле зрения, чего в QML
              // приходилось добиваться руками (ensureVisible).
              className="h-[380px] w-full resize-none bg-transparent px-4 py-4 font-sans text-md leading-[1.4] text-text placeholder:text-text-faint"
            />
          </Card>

          {/* Действия: слева «Привести в порядок» и «Скопировать всё» с жалобой
              рядом, справа - «Удалить». */}
          <div className="flex items-center gap-2">
            <Button
              label={busy ? t("Причёсываю…") : t("Привести в порядок")}
              disabled={busy || text.trim().length === 0}
              onClick={() => {
                setBusy(true);
                // ВЫЗОВ B.tidyNote(id, текст) - ответ придёт сигналом
                // noteTidied, см. подписку выше.
                void tidyNote(current, text);
              }}
            />
            <Button
              label={t("Скопировать всё")}
              disabled={text.trim().length === 0}
              // ВЫЗОВ B.copyText(текст).
              onClick={() => void copyText(text)}
            />
            {/* Почему «Привести в порядок» могло не сработать - словами. Текст
                исключения при этом остаётся в журнале. */}
            {note ? (
              <p role="status" className="font-sans text-sm text-danger">
                {note}
              </p>
            ) : null}
            <Button
              className="ml-auto"
              label={t("Удалить")}
              kind="danger"
              disabled={current === ""}
              // Удалили из редактора - к списку БЕЗ сохранения: иначе
              // backToList пересоздал бы только что удалённую заметку.
              onClick={async () => {
                await deleteNote(current);
                setCurrent("");
                toList();
              }}
            />
          </div>
        </>
      )}
    </>
  );
}
