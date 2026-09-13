// Страница «Диктовка» - самая большая: 743 строки QML, 16 ключей конфига и
// восемь сочетаний клавиш.
//
// Разбита на пять карточек-разделов, как и в QML: сочетания, микрофон, чистка
// текста, вставка, вид. Порядок не алфавитный - сверху то, что настраивают в
// первый день, ниже то, куда заходят раз в жизни.
//
// **Захват сочетания остаётся в Python.** Браузер не отдаст клавишу Win, а
// перехват хоткея внутри вебвью не работает вовсе. Здесь только показ и
// команда «начни захват»; ловит нажатия хук keyboard на стороне Python, и
// результат приезжает сигналом captureDone.
import { useEffect, useState } from "react";

import {
  addAutoEnterApp,
  autoEnterApps,
  cancelCapture,
  getSetting,
  llmBusy,
  llmInstall,
  llmState,
  micOptions,
  on,
  pickInboxPath,
  punctBusy,
  punctModelInstall,
  punctModelReady,
  removeAutoEnterApp,
  pillOptions,
  pretty,
  runningApps,
  setSetting,
  setTechTerms,
  startCapture,
  themeOptions,
  type SettingKey,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { FlowInput } from "../ui/form/input";
import { Segmented } from "../ui/form/segmented";
import { Select } from "../ui/form/select";
import { ToggleRow } from "../ui/form/toggle";
import { HotkeyField } from "../ui/misc/hotkey-field";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";

/** Готовый вариант выпадающего списка - как их отдаёт Backend. */
interface Option {
  value: string;
  label: string;
}

/**
 * Вариант списка микрофонов. Значение тут НЕ строка: у «по умолчанию» это
 * null, у настоящих устройств - номер. Приводить их к строке нельзя - в
 * конфиг уехало бы "0" вместо 0 и "null" вместо пустоты, и микрофон
 * перестал бы выбираться совсем.
 *
 * Radix при этом умеет только строковые значения, и пустую строку считает
 * за «не выбрано». Поэтому наружу отдаём служебный ключ, а внутрь
 * возвращаем исходное значение как есть.
 */
interface DeviceOption {
  value: number | null;
  label: string;
}

const DEFAULT_MIC = "__default__";

/** Настройка в состоянии компонента: читаем один раз, пишем сразу.
 *
 * Ключ типизирован SettingKey, а не string, и это не педантизм: union из 53
 * ключей означает, что опечатка в имени настройки падает на tsc, а не
 * оборачивается тихо неработающим переключателем в готовом окне.
 */
function useSetting<T>(key: SettingKey, fallback: T) {
  const [value, setValue] = useState<T>(fallback);
  useEffect(() => {
    void getSetting(key).then((v) => {
      if (v !== null && v !== undefined) setValue(v as T);
    });
  }, [key]);
  const write = (next: T) => {
    setValue(next);
    setSetting(key, next);
  };
  return [value, write] as const;
}

/**
 * Сочетание клавиш. Захват идёт в Python, сюда приезжает результат.
 *
 * Отписка от сигнала обязательна: страницу можно уйти и вернуться, а
 * подписки копились бы, и одно нажатие писало бы настройку столько раз,
 * сколько раз человек открывал раздел.
 */
function Hotkey({
  field,
  allowClear = true,
}: {
  field: SettingKey;
  allowClear?: boolean;
}) {
  const [value, setValue] = useState("");
  const [capturing, setCapturing] = useState(false);

  // Показываем то, что вернул pretty(), а не то, что лежит в конфиге. В
  // конфиге запись машинная - «ctrl+shift+space», - и человеку её показывать
  // нельзя: HotkeyField по своему договору ждёт уже человеческий вид, и
  // мастер первого запуска так и делает. Здесь этого не хватало, и в окне
  // настроек сочетание выглядело сырой строкой.
  useEffect(() => {
    let alive = true;
    void getSetting(field).then(async (v) => {
      const spec = String(v ?? "");
      const shown = spec ? String((await pretty(spec)) || spec) : "";
      if (alive) setValue(shown);
    });
    const off = on("captureDone", async (which, spec) => {
      if (String(which) !== field) return;
      setCapturing(false);
      const raw = String(spec ?? "");
      setValue(raw ? String((await pretty(raw)) || raw) : "");
    });
    return () => {
      alive = false;
      off();
    };
  }, [field]);

  return (
    <HotkeyField
      field={field}
      value={value}
      capturing={capturing}
      allowClear={allowClear}
      onStartCapture={() => {
        setCapturing(true);
        void startCapture(field);
      }}
      onClear={() => {
        setValue("");
        setSetting(field, "");
        if (capturing) {
          setCapturing(false);
          void cancelCapture();
        }
      }}
    />
  );
}

export function DictationPage() {
  return (
    <>
      <Heading level="page">{t("Диктовка")}</Heading>
      <Hotkeys />
      <Microphone />
      <Cleanup />
      <Insertion />
      <Look />
    </>
  );
}

// ---------- сочетания ----------

function Hotkeys() {
  const [inbox, setInbox] = useSetting("inbox_path", "");

  return (
    <section className="flex flex-col gap-3">
      <Heading>{t("Сочетания")}</Heading>

      <Card>
        <SettingRow
          first
          title={t("Удерживать и говорить")}
          subtitle={t("Самый простой способ. Можно назначить и боковую кнопку мыши")}
        >
          {/* Единственное сочетание без «убрать»: без него программа немая. */}
          <Hotkey field="hotkey_hold" allowClear={false} />
        </SettingRow>
        <SettingRow
          title={t("Нажать и говорить")}
          subtitle={t("Для долгой диктовки, руки свободны")}
        >
          <Hotkey field="hotkey_toggle" />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow first title={t("Править выделенное голосом")}>
          <Hotkey field="hotkey_command" />
        </SettingRow>
        <SettingRow title={t("Преобразовать текст")}>
          <Hotkey field="hotkey_transform" />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow
          first
          title={t("Открыть заметки")}
          subtitle={t("Страница заметок для длинной диктовки")}
        >
          <Hotkey field="hotkey_notes" />
        </SettingRow>
        <SettingRow
          title={t("Отменить последнюю диктовку")}
          subtitle={t("Стирает вставленное одним нажатием")}
        >
          <Hotkey field="undo_hotkey" />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow
          first
          title={t("Диктовать в буфер")}
          subtitle={t("Текст не вставится - вставите его сами")}
        >
          <Hotkey field="hotkey_clipboard" />
        </SettingRow>
        <SettingRow
          title={t("Диктовать в файл")}
          subtitle={t("Мысль на ходу упадёт в конец файла")}
        >
          <Hotkey field="hotkey_inbox" />
        </SettingRow>
        <SettingRow
          title={t("Файл для диктовки")}
          subtitle={t("Куда писать. Пусто - диктовка в файл выключена")}
        >
          <div className="flex gap-2">
            <FlowInput
              value={inbox}
              onChange={setInbox}
              className="w-[220px]"
            />
            {/* Диалог выбора файла - в Python: у страницы нет доступа к диску,
                и путь из HTML-поля выбора файлов ей всё равно не отдадут. */}
            <Button
              label={t("Выбрать…")}
              onClick={async () => {
                const p = await pickInboxPath();
                if (p) setInbox(String(p));
              }}
            />
          </div>
        </SettingRow>
      </Card>
    </section>
  );
}

// ---------- микрофон ----------

function Microphone() {
  const [device, setDevice] = useSetting<number | null>("mic_device", null);
  const [devices, setDevices] = useState<DeviceOption[]>([]);

  // Список берём у Backend, а не собираем сами: подписи там уже человеческие
  // («по умолчанию · Microphone (Realtek)»), и собирать их второй раз на
  // странице значило бы завести второе место, где они могут разъехаться.
  useEffect(() => {
    void micOptions().then((v) => setDevices((v as DeviceOption[]) ?? []));
  }, []);

  const key = (v: number | null) => (v === null ? DEFAULT_MIC : String(v));

  return (
    <section className="flex flex-col gap-3">
      <Heading>{t("Микрофон")}</Heading>
      <Card>
        <SettingRow
          first
          title={t("Микрофон")}
          subtitle={t("Какой микрофон слушать")}
        >
          <Select
            value={key(device)}
            options={devices.map((d) => ({ value: key(d.value), label: d.label }))}
            label={t("Микрофон")}
            onChange={(picked) => {
              const found = devices.find((d) => key(d.value) === picked);
              setDevice(found ? found.value : null);
            }}
          />
        </SettingRow>
        <ToggleSetting
          path="keep_mic_open"
          title={t("Не терять первое слово")}
          subtitle={t("Микрофон наготове, поэтому начало фразы не обрежется")}
        />
        <ToggleSetting
          path="stream_asr"
          title={t("Разбирать речь на ходу")}
          subtitle={t("Работает, пока вы говорите - ждать не надо")}
        />
      </Card>
    </section>
  );
}

// ---------- чистка ----------

function Cleanup() {
  const [url, setUrl] = useSetting("llm.url", "");
  const [model, setModel] = useSetting("llm.model", "");
  const [state, setState] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void llmState().then((v) => setState(String(v ?? "")));
    void llmBusy().then((v) => setBusy(v === true));
    return on("llmDone", () => {
      setBusy(false);
      void llmState().then((v) => setState(String(v ?? "")));
    });
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <Heading>{t("Чистка текста")}</Heading>
      <Card>
        <ToggleSetting
          first
          path="voice_commands"
          title={t("Голосовые команды")}
          subtitle={t("«С новой строки», «нажми энтер» - вслух")}
        />
        <ToggleSetting
          path="llm.enabled"
          title={t("Правка текста на ходу")}
          subtitle={t("Сказали «в пятницу, нет, в субботу» - останется суббота")}
        />
        <SettingRow title={t("Правка текста моделью")} subtitle={state}>
          <Button
            label={busy ? t("Ставится…") : t("Установить")}
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void llmInstall();
            }}
          />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow first title={t("Адрес Ollama")}>
          <FlowInput value={url} onChange={setUrl} mono className="w-[220px]" />
        </SettingRow>
        <SettingRow
          title={t("Модель Ollama")}
          subtitle={t("Оставьте пусто - найдём подходящую сами")}
        >
          <FlowInput value={model} onChange={setModel} className="w-[220px]" />
        </SettingRow>
      </Card>
    </section>
  );
}

// ---------- вставка ----------

function Insertion() {
  const [cleanup, setCleanup] = useSetting("cleanup", "medium");
  const [punct, setPunct] = useSetting("punctuation", "rules");
  const [terms, setTerms] = useSetting("tech_terms", false);
  const [uiLang, setUiLang] = useSetting("ui_language", "ru");
  const [notesOpen, setNotesOpen] = useSetting("notes_open", "list");
  const [punctReady, setPunctReady] = useState(false);
  const [punctLoading, setPunctLoading] = useState(false);
  const [apps, setApps] = useState<Array<{ exe: string; title?: string }>>([]);

  useEffect(() => {
    void punctModelReady().then((v) => setPunctReady(v === true));
    void punctBusy().then((v) => setPunctLoading(v === true));
    void runningApps().then((v) => setApps((v as typeof apps) ?? []));
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <Heading>{t("Вставка")}</Heading>

      <Card>
        <ToggleSetting
          first
          path="smart_join"
          title={t("Продолжать мысль")}
          subtitle={t("Вторая фраза приклеится к первой правильно")}
        />
        <SettingRow
          title={t("Отправлять сообщение")}
          subtitle={t("После вставки нажимать Enter - для чатов")}
        >
          <AutoEnter apps={apps} onChanged={() =>
            void runningApps().then((v) => setApps((v as typeof apps) ?? []))} />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow
          first
          title={t("Насколько править")}
          subtitle={t("От «как услышали» до «править моделью»")}
        >
          <Segmented
            value={cleanup}
            label={t("Насколько править")}
            onChange={setCleanup}
            options={[
              { label: t("ничего"), value: "none" },
              { label: t("слегка"), value: "light" },
              { label: t("обычно"), value: "medium" },
              { label: t("сильно"), value: "high" },
            ]}
          />
        </SettingRow>

        <SettingRow title={t("Знаки препинания")}>
          <div className="flex items-center gap-2">
            <Segmented
              value={punct}
              label={t("Знаки препинания")}
              onChange={setPunct}
              options={[
                { label: t("правила"), value: "rules" },
                { label: t("модель"), value: "model" },
              ]}
            />
            {punct === "model" && !punctReady ? (
              <Button
                label={punctLoading ? t("Качается…") : t("Скачать")}
                disabled={punctLoading}
                onClick={() => {
                  setPunctLoading(true);
                  void punctModelInstall();
                }}
              />
            ) : null}
          </div>
        </SettingRow>

        <SettingRow
          title={t("Технические термины")}
          subtitle={t("«Джейсон» станет JSON, «гитхаб» - GitHub")}
        >
          <Segmented
            value={terms}
            label={t("Технические термины")}
            // Не setSetting: у терминов свой слот, он ещё и словарь
            // перечитывает. Записать ключ напрямую значило бы включить
            // настройку, оставив словарь незаряженным.
            onChange={(v) => {
              setTerms(v);
              void setTechTerms(v);
            }}
            options={[
              { label: t("выключены"), value: false },
              { label: t("включены"), value: true },
            ]}
          />
        </SettingRow>
      </Card>

      <Card>
        <SettingRow
          first
          title={t("Язык интерфейса")}
          subtitle={t("Распознавание остаётся русским - меняются только надписи")}
        >
          <Segmented
            value={uiLang}
            label={t("Язык интерфейса")}
            onChange={setUiLang}
            options={[
              { label: "Русский", value: "ru" },
              { label: "English", value: "en" },
            ]}
          />
        </SettingRow>
        <SettingRow
          title={t("Заметки открываются")}
          subtitle={t("Что показать при открытии")}
        >
          <Segmented
            value={notesOpen}
            label={t("Заметки открываются")}
            onChange={setNotesOpen}
            options={[
              { label: t("списком"), value: "list" },
              { label: t("прошлой"), value: "last" },
              { label: t("новой"), value: "new" },
            ]}
          />
        </SettingRow>
      </Card>
    </section>
  );
}

/**
 * Программы, после вставки в которые жать Enter, - для чатов.
 *
 * Два списка, и путать их нельзя: `runningApps` - что запущено прямо сейчас,
 * из него выбирают; `autoEnterApps` - что уже назначено, его показывают с
 * кнопкой «убрать». В QML это тоже два разных источника, и слить их в один
 * значило бы терять назначенную программу, как только её закроют.
 */
function AutoEnter({
  apps,
  onChanged,
}: {
  apps: Array<{ exe: string; title?: string }>;
  onChanged: () => void;
}) {
  const [pick, setPick] = useState("");
  const [chosen, setChosen] = useState<Array<{ exe: string; title?: string }>>([]);

  async function reloadChosen() {
    const v = await autoEnterApps();
    setChosen((v as typeof chosen) ?? []);
  }

  useEffect(() => {
    void reloadChosen();
  }, []);

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex gap-2">
        <Select
          value={pick}
          label={t("Программа")}
          onChange={setPick}
          options={apps.map((a) => ({ value: a.exe, label: a.title || a.exe }))}
        />
        <Button
          label={t("Добавить")}
          disabled={!pick}
          onClick={async () => {
            await addAutoEnterApp(pick);
            onChanged();
            void reloadChosen();
          }}
        />
      </div>

      {chosen.length ? (
        <ul className="flex flex-col items-end gap-1">
          {chosen.map((a) => (
            <li key={a.exe} className="flex items-center gap-2">
              <span className="font-sans text-sm text-text-muted">
                {a.title || a.exe}
              </span>
              <Button
                label={t("Убрать")}
                onClick={async () => {
                  await removeAutoEnterApp(a.exe);
                  void reloadChosen();
                }}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// ---------- вид ----------

function Look() {
  const [theme, setTheme] = useSetting("theme", "system");
  const [pos, setPos] = useSetting("overlay_position", "bottom");
  const [themes, setThemes] = useState<Option[]>([]);
  const [pills, setPills] = useState<Option[]>([]);

  // Подписи вариантов живут в Python (settings_qt.themeOptions, pillOptions).
  // Здесь их не дублируем: разъедутся - и в одном окне «Система», в другом
  // «Системная», а заметит это владелец, не тест.
  useEffect(() => {
    void themeOptions().then((v) => setThemes((v as Option[]) ?? []));
    void pillOptions().then((v) => setPills((v as Option[]) ?? []));
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <Heading>{t("Вид")}</Heading>
      <Card>
        <SettingRow
          first
          title={t("Оформление")}
          subtitle={t("«Система» - как в Windows")}
        >
          <Segmented
            value={theme}
            label={t("Оформление")}
            onChange={setTheme}
            options={themes}
          />
        </SettingRow>
        <SettingRow
          title={t("Полоска во время записи")}
          subtitle={t("Волна внизу экрана, пока вы говорите")}
        >
          <Segmented
            value={pos}
            label={t("Полоска во время записи")}
            onChange={setPos}
            options={pills}
          />
        </SettingRow>
      </Card>
    </section>
  );
}

/** Переключатель, привязанный к ключу конфига. */
function ToggleSetting({
  path,
  title,
  subtitle,
  first = false,
}: {
  path: SettingKey;
  title: string;
  subtitle?: string;
  first?: boolean;
}) {
  const [value, setValue] = useSetting(path, false);
  return (
    <ToggleRow
      first={first}
      title={title}
      subtitle={subtitle}
      checked={value === true}
      onChange={setValue}
    />
  );
}
