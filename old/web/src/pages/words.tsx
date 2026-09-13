// Страница «Слова»: свой словарь, подстановки и преобразования.
//
// Бывшие «Словарь» и «Замены». Словарь Dragon продаёт за 700 долларов - наш
// виден и объяснён, а не спрятан за термином.
//
// Ключей конфига у страницы нет, поэтому сверка config.json на ней не ловит
// ничего. Всё держится на втором критерии фазы 4 - семь вызовов Backend
// (setDictionary, snippetPresets, setSnippetPreset, setSnippetPresetValue,
// transformPresets, setTransformShown, clearDeclined) должны делать то же, что
// в QML-версии. Каждый ниже помечен.
//
// Сверх них страница ведёт две таблицы. В QML PairTable и TransformTable сами
// ходили в Backend (B.pairs/setPairs, B.customTransforms/setCustomTransforms);
// здесь они управляемые - данные и обработчик приходят снаружи, - и в мост
// ходит страница. Список вызовов от этого не изменился, изменилось место.
//
// ---- Русские строки, которые НЕ переводятся ----
//
// Плейсхолдеры подстановок и имена переменных ({дата} и прочие) остаются
// русскими при любом языке интерфейса: это не текст окна, а значения, которые
// человек впишет в поле буквально. Переведи мы их - и написанное в подсказке
// перестало бы работать. Через t() они пропущены только затем, чтобы проверка
// tools/check_web_i18n.py оставалась строгой на всей остальной странице: без
// перевода в словаре t() возвращает строку как есть. В i18n.py этих ключей
// быть не должно.
import { useEffect, useRef, useState } from "react";

import {
  clearDeclined,
  customTransforms,
  getSetting,
  pairs,
  setCustomTransforms,
  setDictionary,
  setPairs,
  setSnippetPreset,
  setSnippetPresetValue,
  setTransformShown,
  snippetPresets,
  transformPresets,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { FlowInput } from "../ui/form/input";
import { Toggle } from "../ui/form/toggle";
import { Icon, iconForTransform } from "../ui/icons";
import { EmptyState } from "../ui/misc/empty-state";
import { countBlanks, PairTable, type Pair } from "../ui/misc/pair-table";
import {
  countTransformBlanks,
  TransformTable,
  type Transform,
} from "../ui/misc/transform-table";
import { SettingRow } from "../ui/setting-row";
import { Heading, Note } from "../ui/text";

/**
 * Сколько своих преобразований помещается в список.
 *
 * Число живёт в Python (transforms.MAX_CUSTOM) и отдаётся окну как
 * Backend.maxTransforms, но это Property, а не @Slot, и генератор моста таких
 * не печатает - в api.ts его нет. Пока не появится, держим здесь копию:
 * ограничение означает «больше не влезет в список, который выбирают цифрой с
 * клавиатуры», то есть меняться оно может только вместе с этим списком.
 */
const MAX_TRANSFORMS = 12;

/** Строка из B.pairs(): признак `ready` ставит Python. */
interface StoredPair extends Pair {
  ready?: boolean;
}

/** Готовая подстановка-заготовка из B.snippetPresets(). */
interface SnippetPreset {
  id: string;
  /** Фраза диктовки. Русская при любом языке интерфейса. */
  say: string;
  put: string;
  /** Пустую заготовку человек заполняет сам, у готовой значение есть. */
  fill: boolean;
  enabled: boolean;
  value: string;
  preview: string;
}

/** Готовое преобразование из B.transformPresets(). */
interface TransformPreset {
  id: string;
  title: string;
  hint: string;
  shown: boolean;
}

export function WordsPage() {
  const [dict, setDict] = useState("");
  const [dictFocused, setDictFocused] = useState(false);
  const dictField = useRef<HTMLTextAreaElement>(null);

  const [presets, setPresets] = useState<SnippetPreset[]>([]);

  const [rows, setRows] = useState<Pair[]>([]);
  const [ready, setReady] = useState<Pair[]>([]);
  // Пустая ли таблица - решается один раз на загрузку, а не выводится из
  // rows.length. Иначе объяснение над таблицей схлопывалось бы на первой же
  // набранной букве, и поле уезжало бы вверх прямо из-под курсора.
  const [pairsEmpty, setPairsEmpty] = useState(true);

  const [transforms, setTransforms] = useState<Transform[]>([]);
  const [tfPresets, setTfPresets] = useState<TransformPreset[]>([]);
  const [declined, setDeclined] = useState(0);

  useEffect(() => {
    void reloadDict();
    void reloadPresets();
    void reloadPairs();
    void reloadDeclined();
    // ВЫЗОВ B.customTransforms() - свои преобразования.
    void customTransforms().then((v) => setTransforms(v as Transform[]));
    // ВЫЗОВ B.transformPresets() - готовые и то, показываем ли каждое.
    void transformPresets().then((v) => setTfPresets(v as TransformPreset[]));
  }, []);

  // Словарь читаем ключом конфига: B.dictionaryText - это Property, а не
  // @Slot, и в мост он не попал. Склейка та же, что делает Python: слово на
  // строку.
  async function reloadDict() {
    const words = ((await getSetting("dictionary")) ?? []) as string[];
    setDict(words.join("\n"));
  }

  /** ВЫЗОВ B.snippetPresets() - заготовки с текущими значениями. */
  async function reloadPresets() {
    setPresets((await snippetPresets()) as SnippetPreset[]);
  }

  async function reloadPairs() {
    const items = (await pairs("snippets")) as StoredPair[];
    const mine = items.filter((r) => !r.ready).map((r) => ({ k: r.k, v: r.v }));
    setRows(mine);
    setReady(items.filter((r) => r.ready).map((r) => ({ k: r.k, v: r.v })));
    setPairsEmpty(mine.length === 0);
  }

  // Отклонённых находок столько же, сколько записей в ключе конфига:
  // B.declinedCount - снова Property, и считать нечего, кроме длины списка.
  async function reloadDeclined() {
    const list = ((await getSetting("snippets_declined")) ?? []) as unknown[];
    setDeclined(list.length);
  }

  /**
   * Сохранить обе половины таблицы разом.
   *
   * Backend.setPairs собирает словарь ЗАНОВО из присланного. Отправь страница
   * только свои строки - и сотня готовых терминов стёрлась бы от правки одной
   * буквы в чужом поле.
   */
  function commitPairs(next: { rows: Pair[]; ready: Pair[] }) {
    setRows(next.rows);
    setReady(next.ready);
    void setPairs("snippets", [...next.rows, ...next.ready]);
  }

  function commitTransforms(next: Transform[]) {
    setTransforms(next);
    void setCustomTransforms(next);
  }

  const blanks = countBlanks(rows);
  const tfBlanks = countTransformBlanks(transforms);
  const tfFull = transforms.length >= MAX_TRANSFORMS;

  return (
    <>
      <Heading level="page">{t("Слова")}</Heading>

      <div className="flex flex-col gap-3">
        <Heading level="section">{t("Свои слова")}</Heading>
        {/* Объяснение - строкой карточки, а не абзацем над ней. Абзац занимал
            две строки и читался как введение, которое можно пропустить; ряд с
            «подробнее» отвечает на «что сюда писать» одной строкой, а
            подробности отдаёт по требованию. */}
        <Card>
          <SettingRow
            first
            icon={<Icon name="dictionary" size={20} />}
            title={t("Что сюда писать")}
            subtitle={t("Фамилии, названия, термины - по одному на строку")}
            more={
              t("Те слова, которые программа слышит, но пишет ") +
              t("неправильно. Дальше она будет писать их так, ") +
              t("как написали вы.")
            }
          />
          {/* Та же волосяная линия, что делит ряды: поле - это вторая часть
              карточки, а не приклеенный к ней ящик. */}
          <div className="relative border-t border-border">
            <textarea
              ref={dictField}
              value={dict}
              onFocus={() => setDictFocused(true)}
              onBlur={() => setDictFocused(false)}
              onChange={(e) => {
                setDict(e.target.value);
                // ВЫЗОВ B.setDictionary(текст) - разбор на слова в Python.
                //
                // В QML тут стояла проверка «поле в фокусе»: присвоение
                // text из привязки тоже дёргало onTextChanged и сохраняло
                // словарь на ровном месте. Здесь onChange срабатывает только
                // от человека, и проверка не нужна.
                void setDictionary(e.target.value);
              }}
              aria-label={t("Свои слова")}
              // Без переноса строк: слово на строку, длинное уезжает вбок, а
              // не разваливается пополам.
              className="h-[300px] w-full resize-none overflow-auto bg-transparent px-4 py-4 font-mono text-2xs leading-[1.6] whitespace-pre text-text"
            />
            {/* Пустой словарь - это триста пикселей белого поля под строкой
                «Фамилии, названия, термины». Отличить его от не загрузившегося
                поля нечем, а на свежей установке он пустой у всех.

                Пропадает не только когда слово вписали, но и как только в поле
                встал курсор: человек уже начал, и приглашение поверх его
                курсора - это помеха. Мышь проходит насквозь, поэтому щелчок по
                пустому полю по-прежнему ставит туда курсор; ловит нажатия
                только кнопка. */}
            {dict.trim() === "" && !dictFocused ? (
              <div className="pointer-events-none absolute inset-x-0 top-2 [&_button]:pointer-events-auto">
                <EmptyState
                  icon="dictionary"
                  title={t("Пока ни одного слова")}
                  hint={
                    t("Впишите фамилию, название или термин - ") +
                    t("по одному на строку. Дальше программа ") +
                    t("будет писать их так же.")
                  }
                  actionLabel={t("Вписать слово")}
                  onAction={() => dictField.current?.focus()}
                />
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      {/* ---- Готовые подстановки ----
          Заготовки на частое: включаешь и вписываешь СВОЁ. Слева фраза уже
          задана, справа пусто - человек заполняет; часть идёт с готовым
          значением через переменные ({дата} и прочие), их вписывать не надо.

          Механика - ровно как у техтерминов: включённая заготовка падает в те
          же snippets, второго хранилища нет. Отличает их список id в
          snippets_presets_on: по нему блок знает, что показать включённым, а
          таблица «Подстановки» ниже - какие фразы не дублировать. Поэтому
          заготовки стоят ВЫШЕ пользовательских, отдельным блоком. */}
      <div className="flex flex-col gap-3">
        <Heading level="section">{t("Готовые подстановки")}</Heading>
        <Card>
          <SettingRow
            first
            icon={<Icon name="swap" size={20} />}
            title={t("Включите и впишите своё")}
            subtitle={t("Частые фразы уже заведены - вам остаётся значение")}
            more={
              t("«Моя почта», «телефон», «подпись» - включите нужное и впишите ") +
              t("один раз. Дальше скажете фразу - вставится ваше. ") +
              t("Заготовки с датой и временем подставят их сами.")
            }
          />
          <ul>
            {presets.map((p) => (
              <li key={p.id}>
                <SettingRow
                  // Фраза БЕЗ перевода: это текст диктовки, он русский в любом
                  // интерфейсе - как ключи подстановок и словарь.
                  title={p.say}
                  subtitle={
                    p.fill
                      ? p.enabled
                        ? t("Ваше значение - в поле справа")
                        : t("Включите и впишите своё")
                      : t("Вставит: ") + p.preview
                  }
                >
                  <div className="flex items-center gap-3">
                    {/* Поле для своего значения - только у пустых заготовок и
                        только когда включены: у готовых (с датой) вписывать
                        нечего, значение уже есть. */}
                    {/* Ширину задаёт обёртка, а не сам контрол: cn() склеивает
                        классы, не разбирая их, и второе width рядом с
                        собственным w-[200px] поля решалось бы порядком правил в
                        готовом CSS, то есть случаем. */}
                    {p.enabled && p.fill ? (
                      <div className="w-[190px]">
                        <FlowInput
                          value={p.value}
                          label={p.say}
                          placeholder={t("ваше значение")}
                          className="w-full"
                          onChange={(v) => {
                            setPresets((list) =>
                              list.map((r) =>
                                r.id === p.id ? { ...r, value: v } : r,
                              ),
                            );
                            // ВЫЗОВ B.setSnippetPresetValue(id, значение).
                            void setSnippetPresetValue(p.id, v);
                          }}
                        />
                      </div>
                    ) : null}
                    <Toggle
                      checked={p.enabled}
                      label={p.say}
                      onChange={async (v) => {
                        // ВЫЗОВ B.setSnippetPreset(id, включено).
                        await setSnippetPreset(p.id, v);
                        // Перечитываем список - обновить галку и значение; и
                        // таблицу ниже, ведь фраза могла уехать в неё
                        // (выключили заполненную) или уйти из неё (включили
                        // свою).
                        void reloadPresets();
                        void reloadPairs();
                      }}
                    />
                  </div>
                </SettingRow>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <Heading level="section">{t("Подстановки")}</Heading>
          <Button
            kind="primary"
            label={t("Добавить")}
            onClick={() => setRows([...rows, { k: "", v: "" }])}
          />
        </div>

        {/* Пояснение ПЕРЕД таблицей, а не после неё.
            Владелец сказал: «подстановки выглядят пусто и непонятно; нужно два
            поля рядом со стрелкой». Поля со стрелкой были и раньше, но увидеть
            их можно было, только нажав «Добавить»: пустая таблица показывала
            одну серую строчку, а объяснение лежало ПОД ней, то есть читалось
            после того, как непонятно уже стало.

            Пока подстановок нет, объяснение развёрнуто в полное пустое
            состояние. Появилась первая - схлопывается в обычный ряд: место на
            странице занимает то, что человек уже понял. */}
        {pairsEmpty ? (
          <Card>
            <EmptyState
              icon="swap"
              title={t("Подстановок пока нет")}
              hint={
                t("Слева впишите, что говорите, справа - что ") +
                t("вставится. Скажете «моя почта» - появится адрес.")
              }
            />
          </Card>
        ) : (
          <Card>
            <SettingRow
              first
              icon={<Icon name="swap" size={20} />}
              title={t("Что на что менять")}
              subtitle={t("Слева - что вы говорите, справа - что вставится")}
              more={
                t("Скажете «моя почта» - появится адрес. ") +
                t("Пустые строки не сохраняются.")
              }
            />
          </Card>
        )}

        <PairTable
          rows={rows}
          ready={ready}
          onChange={commitPairs}
          caption={t("Подстановки")}
          leftHeader={t("Что говорю")}
          rightHeader={t("Что вставится")}
          // Русские значения примера - см. шапку файла: их не переводят.
          leftPlaceholder={t("моя почта")}
          rightPlaceholder="roman@example.com"
          // Пустая таблица показывает не серую надпись, а живую строку: два
          // поля и стрелку между ними. Так видно, что это форма, а не
          // сообщение об ошибке.
          showBlankRow
          // Технические термины лежат в тех же подстановках, и их полторы
          // сотни: включив их, человек переставал находить среди них свои три.
          // «Программа добавила» вместо «системные»: слово «система» ничего не
          // объясняет тому, кто просто пишет письма.
          readyTitle={t("Термины для программирования")}
          readyHint={t("Их добавила программа. Ваши - выше")}
        />

        {/* Живые подстановки внутри подстановки: «подпись» с {дата} вставит
            сегодняшнее число, а не слово «дата». Имена переменных не
            переводятся - см. шапку файла. */}
        <Note>
          {t("В правой части работают: ")}
          {t("{дата}, {дата-словами}, {время}, {день-недели}")}
        </Note>

        {/* Предупреждение о пустых строках - только когда они есть. В общем
            пояснении оно висело всегда и росло до второй строки;
            предупреждению место рядом с бедой. */}
        {blanks > 0 ? (
          <Note>
            {t("Пустых строк:")} {blanks} - {t("они не сохранятся.")}
          </Note>
        ) : null}

        {/* «Не надо» на находке запоминается навсегда - иначе программа
            спрашивала бы одно и то же каждую неделю. Но дверь назад нужна:
            промах мыши не должен стоить находки, о которой потом не узнаешь.
            Строки нет, пока отказываться было не от чего. */}
        {declined > 0 ? (
          <div className="flex items-center gap-3">
            <span className="font-sans text-sm text-text-muted">
              {t("Отклонённых находок:")} {declined}
            </span>
            <Button
              label={t("Предложить снова")}
              onClick={async () => {
                // ВЫЗОВ B.clearDeclined() - забыть отказы.
                await clearDeclined();
                void reloadDeclined();
              }}
            />
          </div>
        ) : null}
      </div>

      {/* ---- Преобразования ----
          Список, который открывается по сочетанию «Преобразовать текст».
          Готовые написали мы, свои пишет человек - и до сих пор мог написать
          их только в config.json, то есть никак. */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <Heading level="section">{t("Свои преобразования")}</Heading>
          {tfFull ? null : (
            <Button
              kind="primary"
              label={t("Добавить")}
              onClick={() =>
                setTransforms([...transforms, { title: "", instruction: "" }])
              }
            />
          )}
        </div>

        {/* Объяснение - до таблицы, по той же причине, что и у подстановок:
            после неё оно читается, когда непонятно уже стало. */}
        <Card>
          <SettingRow
            first
            icon={<Icon name="sparkles" size={20} />}
            title={t("Как этим пользоваться")}
            subtitle={t("Выделите текст, нажмите сочетание, выберите нужное")}
            more={
              t("Слева название, справа что сделать: пишите словами, ") +
              t("как объяснили бы человеку. Список выбирают цифрами, ") +
              t("поэтому больше десяти в него не помещается.")
            }
          />
        </Card>

        <TransformTable rows={transforms} onChange={commitTransforms} />

        {tfFull || tfBlanks > 0 ? (
          <Note>
            {tfFull ? (
              t("Больше не поместится: список выбирают цифрами.")
            ) : (
              <>
                {t("Незаполненных строк:")} {tfBlanks} - {t("они не сохранятся.")}
              </>
            )}
          </Note>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        <Heading level="section">{t("Готовые преобразования")}</Heading>
        <Card>
          <SettingRow
            first
            icon={<Icon name="list" size={20} />}
            title={t("Что показывать в списке")}
            subtitle={t("Выключенное просто не показывается в списке")}
            more={
              t("Чтобы не искать своё среди того, чем не пользуетесь. ") +
              t("Сами преобразования никуда не деваются - их можно ") +
              t("вернуть обратно тем же переключателем.")
            }
          />
          <ul>
            {tfPresets.map((p) => {
              const icon = iconForTransform(p.id);
              return (
                <li key={p.id}>
                  <SettingRow
                    icon={icon ? <Icon name={icon} size={20} /> : undefined}
                    // Название и подсказку пишет Python, переводим их здесь -
                    // ключ перевода тот же, что и у любой строки окна.
                    title={t(p.title)}
                    subtitle={t(p.hint)}
                  >
                    <Toggle
                      checked={p.shown}
                      label={t(p.title)}
                      onChange={(v) => {
                        setTfPresets((list) =>
                          list.map((r) =>
                            r.id === p.id ? { ...r, shown: v } : r,
                          ),
                        );
                        // ВЫЗОВ B.setTransformShown(id, показывать).
                        void setTransformShown(p.id, v);
                      }}
                    />
                  </SettingRow>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </>
  );
}
