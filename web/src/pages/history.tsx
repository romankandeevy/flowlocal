// Страница «История»: что было надиктовано, с поиском.
//
// Первая перенесённая страница, и выбрана она нарочно самой маленькой: 173
// строки, один ключ конфига и три вызова Backend. На ней обкатываются оба
// критерия готовности фазы 4 - и сверка config.json, и ручной проход по
// вызовам, - прежде чем браться за «Диктовку» с её шестнадцатью ключами.
//
// Поиск фильтрует уже полученный список, а не ходит в Python на каждую букву.
// Так же было в QML, и по той же причине: история целиком приезжает одним
// вызовом, она невелика, а запрос на каждое нажатие клавиши превратил бы
// набор в подёргивание.
import { useEffect, useMemo, useState } from "react";

import { clearHistory, copyText, historyData } from "../bridge/api";
import { getSetting, setSetting } from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { EmptyState } from "../ui/misc/empty-state";
import { FlowInput } from "../ui/form/input";
import { SettingRow } from "../ui/setting-row";
import { Toggle } from "../ui/form/toggle";
import { Heading, Note } from "../ui/text";

interface Row {
  when: string;
  dur: string;
  words: string;
  text: string;
  fromFile?: boolean;
}

export function HistoryPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [note, setNote] = useState("");
  const [query, setQuery] = useState("");
  const [keep, setKeep] = useState(true);

  async function reload() {
    const d = (await historyData()) as { rows?: Row[]; note?: string };
    setRows(d?.rows ?? []);
    setNote(String(d?.note ?? ""));
  }

  useEffect(() => {
    void reload();
    void getSetting("history").then((v) => setKeep(v === true));
  }, []);

  const shown = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return rows;
    return rows.filter((r) => String(r.text).toLowerCase().includes(q));
  }, [rows, query]);

  return (
    <>
      <Heading level="page">{t("История")}</Heading>

      <Card>
        <SettingRow
          first
          title={t("Вести историю")}
          subtitle={t("Выключите - и программа не будет ничего запоминать")}
        >
          <Toggle
            checked={keep}
            label={t("Вести историю")}
            onChange={(v) => {
              setKeep(v);
              setSetting("history", v);
            }}
          />
        </SettingRow>
      </Card>

      <div className="flex gap-2">
        <FlowInput
          value={query}
          onChange={setQuery}
          placeholder={t("Найти в надиктованном…")}
          className="flex-1"
        />
        <Button label={t("Обновить")} onClick={() => void reload()} />
        <Button
          label={t("Очистить")}
          kind="danger"
          onClick={async () => {
            await clearHistory();
            void reload();
          }}
        />
      </div>

      {note ? <Note>{note}</Note> : null}

      {shown.length === 0 ? (
        <EmptyState
          title={
            rows.length === 0
              ? t("Пока ничего не надиктовано")
              : t("Ничего не нашлось")
          }
          hint={
            rows.length === 0
              ? t("Зажмите сочетание и скажите фразу - она появится здесь.")
              : t("Попробуйте другое слово.")
          }
        />
      ) : (
        // list, а не просто набор карточек: диктор объявляет «список, 12
        // элементов» и умеет по нему прыгать. В QML это ListView, и для
        // диктора он немой.
        <ul className="flex flex-col gap-3">
          {shown.map((r, i) => (
            <li key={`${r.when}-${i}`}>
              {/* Тень выключена: карточек в списке бывают десятки, и каждая
                  подняла бы свой слой на композитор. */}
              <Card shadow={false}>
                <div className="flex flex-col gap-2.5 px-5 py-3.5">
                  <div className="truncate font-mono text-2xs text-text-muted">
                    {[r.when, r.dur, r.words, r.fromFile ? t("из файла") : ""]
                      .filter(Boolean)
                      .join("   ·   ")}
                  </div>
                  {/* data-selectable: своё окно текст мышью не выделяет, но
                      расшифровку человек как раз захочет скопировать руками. */}
                  <p
                    data-selectable
                    className="text-md leading-[1.35] whitespace-pre-wrap text-text"
                  >
                    {r.text}
                  </p>
                  <div>
                    <Button
                      label={t("Скопировать")}
                      onClick={() => void copyText(r.text)}
                    />
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
