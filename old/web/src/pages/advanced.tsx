// Страница «Дополнительно»: не свалка тумблеров, а список симптомов.
//
// Каждый заголовок здесь задаёт вопрос, с которым сюда приходят: «Текст не
// появляется?», «Записывает само?». Настройка под вопросом - это ответ. Отсюда
// и порядок: сначала то, что чинят, потом «Мелочи» - то, что меняют по вкусу и
// что поломкой не бывает.
//
// **Списки вариантов читаются как свойства, а не как методы.** insertOptions,
// modelOptions и deviceOptions объявлены в Backend через Q_PROPERTY, поэтому
// обёртки в api.ts у них нет - gen_bridge.py печатает только @Slot. Мост читать
// их умеет тем же `call` без аргументов (bridge.py, Bridge._do_call), и это не
// обход правил, а прямо описанный там путь. Держать копию списков на странице
// нельзя: каталог моделей меняется между версиями, и копия разъедется молча.
//
// Подписи вариантов приезжают из Python по-русски и переводятся здесь, на
// показе. Так же поступает QML (Segmented.qml: `L.t(modelData.label)`) - t()
// идемпотентен, и то, что уже прошло перевод, второй раз не портится.
import { useEffect, useState } from "react";

import {
  deleteModel,
  dmlRun,
  dmlState,
  downloadModel,
  getSetting,
  modelsInfo,
  on,
  setModel,
  setRestart,
  setSetting,
  type SettingKey,
} from "../bridge/api";
import { call } from "../bridge/client";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { cn } from "../ui/cn";
import { Segmented } from "../ui/form/segmented";
import { Slider } from "../ui/form/slider";
import { ToggleRow } from "../ui/form/toggle";
import { Icon } from "../ui/icons";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";

/** Вариант выбора из Backend: подпись по-русски, значение - код. */
interface Opt {
  label: string;
  value: string;
}

/** Модель в каталоге - то, что отдаёт Backend.modelsInfo(). */
interface ModelRow {
  id: string;
  title: string;
  sizeMb: number;
  onDiskMb: number;
  installed: boolean;
  active: boolean;
  downloading: boolean;
}

/** Что показывать в ряду про видеокарту до первого нажатия. */
interface DmlState {
  /** Непусто - нажимать бессмысленно, и здесь же сказано почему. */
  why: string;
  installed: boolean;
  active: boolean;
}

/** Настройка в состоянии страницы: читаем один раз, пишем сразу. */
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

/** Список вариантов из Q_PROPERTY Backend. */
function useOptions(name: string): Opt[] {
  const [opts, setOpts] = useState<Opt[]>([]);
  useEffect(() => {
    void call(name).then((v) => {
      const list = (v as Opt[] | null) ?? [];
      setOpts(list.map((o) => ({ label: String(o.label), value: String(o.value) })));
    });
  }, [name]);
  return opts;
}

/** Подписи вариантов - на язык интерфейса. */
function shown(opts: Opt[]): Opt[] {
  return opts.map((o) => ({ label: t(o.label), value: o.value }));
}

// Секунды словами: «0.32 с». Три знака после запятой - это отчёт, человеку
// хватает двух.
function sec(v: unknown): string {
  const n = Number(v);
  return n ? n.toFixed(2) + " " + t("с") : "?";
}

// Отказы приезжают из dml_setup строчными: там они работают ещё и этапами
// («скачиваю», «ставлю»), а этапы пишутся с маленькой. В подписи это уже
// предложение, и начинаться оно обязано с большой.
function cap(s: string): string {
  return s === "" ? "" : s.charAt(0).toUpperCase() + s.slice(1);
}

export function AdvancedPage() {
  const [insertMode, setInsertMode] = useSetting<string>("insert_mode", "paste");
  const [preBuffer, setPreBuffer] = useSetting<number>("pre_buffer_sec", 0);
  const [minRecord, setMinRecord] = useSetting<number>("min_record_sec", 0.3);
  const [english, setEnglish] = useSetting<boolean>("english_speech", false);
  const [appendSpace, setAppendSpace] = useSetting<boolean>("append_space", true);
  const [restore, setRestore] = useSetting<boolean>("restore_clipboard", true);
  const [sounds, setSounds] = useSetting<boolean>("sounds", true);
  const [layout, setLayout] = useSetting<string>("layout", "cards");

  // Модель и устройство пишутся не через set: у первой Backend меняет заодно
  // квантизацию и просит приложение перегрузить модель на ходу, у второго -
  // предупреждает, что применится после перезапуска. Поэтому местное состояние
  // здесь своё, а запись идёт своим вызовом.
  const [model, setModelValue] = useState("");
  const [device, setDevice] = useState("");

  const insertOpts = useOptions("insertOptions");
  const modelOpts = useOptions("modelOptions");
  const deviceOpts = useOptions("deviceOptions");

  const [disk, setDisk] = useState<ModelRow[]>([]);

  useEffect(() => {
    void getSetting("model").then((v) => setModelValue(String(v ?? "")));
    void getSetting("device").then((v) => setDevice(String(v ?? "")));
  }, []);

  useEffect(() => {
    const load = () => {
      void modelsInfo().then((v) => setDisk(((v as ModelRow[] | null) ?? [])));
    };
    load();
    // Два сигнала, как и в QML: modelsChanged приходит на скачивание и удаление,
    // changed - на смену выбранной модели. Строка «используется» стоит на той же
    // карточке и обязана переехать вместе с выбором, иначе врёт до закрытия окна.
    const offModels = on("modelsChanged", load);
    const offChanged = on("changed", load);
    return () => {
      offModels();
      offChanged();
    };
  }, []);

  return (
    <>
      <Heading level="page">{t("Дополнительно")}</Heading>

      <Heading>{t("Если что-то не так")}</Heading>

      {/* Первая карточка - беды вокруг нажатия и вставки. */}
      <Card>
        <SettingRow
          first
          icon={<Icon name="clipboard" size={20} />}
          title={t("Текст не появляется?")}
          subtitle={t("По одной букве медленнее, зато доходит куда угодно")}
          more={
            t("Сразу целиком - мгновенно и подходит почти везде. ") +
            t("По одной букве медленнее, зато доходит туда, ") +
            t("куда первое не доходит")
          }
        >
          <Segmented
            options={shown(insertOpts)}
            value={insertMode}
            label={t("Текст не появляется?")}
            onChange={setInsertMode}
          />
        </SettingRow>

        <SettingRow
          icon={<Icon name="history" size={20} />}
          title={t("Первое слово обрезается?")}
          subtitle={t("Сдвиньте вправо - микрофон включится раньше нажатия")}
        >
          {/* Пишем на отпускании, а не на каждом шаге: пока ручку ведут,
              значений набегает три десятка, и каждое было бы записью в
              config.json. Человек видит число всё это время - его показывает
              сам ползунок. */}
          <Slider
            from={0}
            to={1.5}
            step={0.1}
            value={preBuffer}
            label={t("Первое слово обрезается?")}
            onChange={(v) => setPreBuffer(v)}
            onCommit={(v) => setSetting("pre_buffer_sec", v)}
          />
        </SettingRow>

        {/* Признак называем прямо: решает длина нажатия, и ничего больше.
            Число не повторяем - его показывает сам ползунок. */}
        <SettingRow
          icon={<Icon name="timer" size={20} />}
          title={t("Записывает само?")}
          subtitle={t("Решает длина нажатия: короче - промах, а не диктовка")}
          more={t("Задели клавишу мимоходом - записи не будет")}
        >
          <Slider
            from={0.1}
            to={1.5}
            step={0.1}
            value={minRecord}
            label={t("Записывает само?")}
            onChange={(v) => setMinRecord(v)}
            onCommit={(v) => setSetting("min_record_sec", v)}
          />
        </SettingRow>
      </Card>

      {/* Вторая - беды распознавания. Отдельной карточкой, потому что сюда же
          входит справка «что лежит на диске»: в общей она читалась бы
          продолжением ползунков про доли секунды. */}
      <Card>
        {/* Переключатель, а не список с карточками и кнопками скачивания.
            Моделей осталось две, и обе - GigaAM: выбирать тут нечего, кроме
            «побыстрее» и «поаккуратнее». */}
        <SettingRow
          first
          icon={<Icon name="target" size={20} />}
          title={t("Слова распознаются неточно?")}
          subtitle={t("Внимательная аккуратнее с окончаниями и редкими словами")}
          more={
            t("Обычная подходит почти всем. Переключается на ходу: ") +
            t("старая работает, пока грузится новая")
          }
        >
          <Segmented
            options={shown(modelOpts)}
            value={model}
            label={t("Слова распознаются неточно?")}
            onChange={(v) => {
              setModelValue(v);
              void setModel(v);
            }}
          />
        </SettingRow>

        {/* Что лежит на диске. Строки отвечают на два вопроса сразу: сколько
            места занято и что будет, если переключиться на вторую модель
            (скачается 238 МБ, и лучше знать это заранее, чем в дороге).

            Своим блоком, а не в общем ряду. Вся страница здесь - вопросы-
            симптомы. «Обычная - используется · 236 МБ на диске» стояла между
            двумя такими вопросами и читалась как третий, то есть как настройка,
            которую человек должен решить. Решать тут нечего: это справка к
            переключателю выше. Подзаголовок и отступ слева говорят это
            раскладкой: блок продолжает предыдущий ответ, а не начинает свой
            вопрос. Верхней линии у него намеренно нет - она отрезала бы его от
            строки, к которой он относится. */}
        <div className="pb-6 pl-6">
          <Heading className="mb-1">{t("Что лежит на диске")}</Heading>
          {/* list, а не набор строк: диктор объявляет «список, 2 элемента» и
              умеет по нему прыгать. */}
          <ul>
            {disk.map((m, i) => (
              <li key={m.id}>
                <SettingRow
                  first={i === 0}
                  icon={<Icon name="disk" size={20} />}
                  title={t(m.title)}
                  subtitle={
                    m.active
                      ? t("используется") + " · " + m.onDiskMb + " " + t("МБ на диске")
                      : m.downloading
                        ? t("качается…")
                        : m.installed
                          ? t("скачана, лежит про запас") + " · " + m.onDiskMb + " " + t("МБ")
                          : t("не скачана - скачается") +
                            " " +
                            m.sizeMb +
                            " " +
                            t("МБ при первом включении")
                  }
                >
                  {!m.active && !m.downloading ? (
                    <Button
                      label={m.installed ? t("Удалить") : t("Скачать")}
                      onClick={() => {
                        if (m.installed) void deleteModel(m.id);
                        else void downloadModel(m.id);
                      }}
                    />
                  ) : null}
                </SettingRow>
              </li>
            ))}
          </ul>
        </div>

        <SettingRow
          icon={<Icon name="gauge" size={20} />}
          title={t("Распознавание медленное?")}
          subtitle={t("«Авто» выбирает само. Видеокарта быстрее, если есть")}
        >
          <Segmented
            options={shown(deviceOpts)}
            value={device}
            label={t("Распознавание медленное?")}
            onChange={(v) => {
              setDevice(v);
              void setRestart("device", v);
            }}
          />
        </SettingRow>

        <DmlRow onDevice={setDevice} />

        {/* Выключатель, а не способ включить. Английский работает сразу и без
            единого действия: модель приезжает вместе с основной в мастере
            первого запуска. Строка здесь нужна ровно на один случай - когда
            программа приняла русскую фразу за английскую, и человек ищет, чем
            это унять. Поэтому и страница эта, «Если что-то не так». */}
        <ToggleRow
          icon={<Icon name="languages" size={20} />}
          title={t("Английская речь")}
          subtitle={t("Скажете по-английски - программа так и напишет")}
          more={
            t("Программа сама слышит, что фраза английская, и пишет ") +
            t("её буквами. Приняла за английскую русскую фразу - ") +
            t("выключите здесь")
          }
          checked={english}
          onChange={setEnglish}
        />
      </Card>

      {/* Мелочи - не симптомы. Их держим отдельной карточкой, чтобы человек,
          пришедший чинить, не принял их за причину беды. */}
      <Heading>{t("Мелочи")}</Heading>
      <Card>
        <ToggleRow
          first
          icon={<Icon name="space" size={20} />}
          title={t("Пробел в конце")}
          subtitle={t("Чтобы следующая фраза не слиплась с этой")}
          checked={appendSpace}
          onChange={setAppendSpace}
        />
        <ToggleRow
          icon={<Icon name="copy" size={20} />}
          title={t("Не трогать скопированное")}
          subtitle={t("Вернём на место то, что вы копировали до диктовки")}
          checked={restore}
          onChange={setRestore}
        />
        <ToggleRow
          icon={<Icon name="sound" size={20} />}
          title={t("Звуковые сигналы")}
          subtitle={t("Тихий сигнал, когда запись началась и закончилась")}
          checked={sounds}
          onChange={setSounds}
        />
        {/* Было «Расположение: карточками / строками». Владелец спросил
            «расположение ЧЕГО?» и сам же ответил точнее нас: разница только в
            фоне у элементов, ничего никуда не переставляется. Так и называем. */}
        <SettingRow
          icon={<Icon name="surface" size={20} />}
          title={t("Фон под настройками")}
          subtitle={t("С фоном - карточками, без фона - строками")}
          more={
            t("С фоном настройки лежат карточками, без фона - ") +
            t("строками через линию. Второе плотнее")
          }
        >
          <Segmented
            options={[
              { label: t("есть"), value: "cards" },
              { label: t("нет"), value: "lines" },
            ]}
            value={layout || "cards"}
            label={t("Фон под настройками")}
            onChange={setLayout}
          />
        </SettingRow>
      </Card>
    </>
  );
}

/**
 * Проба видеокарты - продолжение строки «Распознавание медленное?», а не своя
 * настройка: там человек ВЫБИРАЕТ, чем считать, здесь выясняет, есть ли из чего
 * выбирать. Вид взят у установки Ollama на «Диктовке»: полоса, точка цветом,
 * слово рядом. Одинаковые по смыслу вещи в программе должны выглядеть
 * одинаково, а «долгая установка с этапами» здесь уже была.
 *
 * Кнопка честно сообщает и о неудаче. Замер решает сам, и на машине автора он
 * говорит «медленнее» - см. шапку dml_setup.py. Поэтому «не помогло» здесь
 * такой же законный итог, как «помогло», и подпись под него написана заранее.
 *
 * Своим компонентом, а не куском страницы: у ряда семь состояний и две подписки
 * на сигналы, и держать их в состоянии всей страницы значило бы перерисовывать
 * её целиком на каждый кадр полосы.
 */
function DmlRow({ onDevice }: { onDevice: (device: string) => void }) {
  const [st, setSt] = useState<DmlState>({ why: "", installed: false, active: false });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [ok, setOk] = useState(false);
  const [fail, setFail] = useState("");
  const [stage, setStage] = useState("");
  const [frac, setFrac] = useState(0);
  const [res, setRes] = useState<Record<string, unknown>>({});

  // Нельзя вовсе (сборка, не Windows) - строка остаётся объяснением без кнопки.
  // Прятать её нечестно: человек читал про видеокарту в README и пришёл сюда
  // искать.
  const can = st.why === "";

  useEffect(() => {
    void dmlState().then((v) => setSt(v as unknown as DmlState));
  }, []);

  useEffect(() => {
    const offStage = on("dmlStage", (name, part) => {
      setBusy(true);
      setStage(String(name));
      setFrac(Number(part));
    });
    const offDone = on("dmlDone", (good, why, result) => {
      setBusy(false);
      setOk(Boolean(good));
      setFail(String(why));
      setRes(result);
      setDone(String(why) === "");
      void dmlState().then((v) => setSt(v as unknown as DmlState));
      // Замер сам решает, чем считать, и записывает это в настройку строкой
      // выше. Без этой строчки переключатель показывал бы «авто» после того,
      // как мы прибили «процессор», - то есть врал бы про собственное состояние.
      void getSetting("device").then((v) => onDevice(String(v ?? "")));
    });
    return () => {
      offStage();
      offDone();
    };
  }, [onDevice]);

  // «Не помогло» - серым, а не красным: это не ошибка, а ответ на вопрос.
  // Красный остаётся тому, что и вправду сломалось, - иначе он перестанет
  // что-либо значить.
  const tone = !can
    ? "text-text-muted"
    : busy
      ? "text-accent"
      : done
        ? ok
          ? "text-success"
          : "text-text-muted"
        : fail !== ""
          ? "text-danger"
          : "text-text-secondary";

  const subtitle = !can
    ? st.why
    : busy
      ? stage || t("проверяю")
      : fail !== ""
        ? cap(fail)
        : done
          ? ok
            ? t("Быстрее") +
              ": " +
              sec(res.cpu) +
              " → " +
              sec(res.gpu) +
              ". " +
              t("Перезапустите программу")
            : t("Видеокарта медленнее") +
              ": " +
              sec(res.gpu) +
              " " +
              t("против") +
              " " +
              sec(res.cpu) +
              ". " +
              t("Оставил процессор")
          : st.active
            ? t("Уже считает видеокарта")
            : // Колесо на диске, а считает всё ещё процессор - значит человек
              // уже нажимал и не перезапустился. Окно к этому моменту закрывали,
              // и весь итог прошлого нажатия пропал вместе с ним; напомнить про
              // перезапуск больше некому.
              st.installed
              ? t("Поставлено. Перезапустите программу")
              : t("Проверим на вашей записи и покажем секунды");

  // Подробности - под шеврон, как везде на этой странице. Длинная запись это
  // отдельная история: на ней видеокарта выигрывает даже когда на короткой
  // проиграла, и человеку, который диктует помногу, надо дать этот факт, а не
  // спрятать его за вердиктом.
  const more =
    done && res.long_gpu
      ? t("На длинной записи видеокарта быстрее: ") +
        sec(res.long_gpu) +
        " " +
        t("против") +
        " " +
        sec(res.long_cpu) +
        ". " +
        t("Диктуете помногу - поставьте «видеокарта» строкой выше")
      : can && !busy
        ? t("Скачаем 26 МБ и подменим часть распознавания. ") +
          t("Замер решит сам: стало медленнее - вернём процессор")
        : "";

  return (
    <SettingRow
      // Молния, а не тот же датчик, что строкой выше: два одинаковых значка
      // подряд читаются как одна настройка.
      icon={<Icon name="zap" size={20} />}
      title={t("Ускорить на видеокарте")}
      subtitle={subtitle}
      more={more || undefined}
    >
      <div className="flex items-center gap-3">
        {busy ? (
          // role="progressbar" с числом: в QML это два прямоугольника, и для
          // диктора они немые - он не сообщает ни что идёт работа, ни сколько
          // осталось.
          <div
            role="progressbar"
            aria-label={t("Ускорить на видеокарте")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(Math.max(0, Math.min(1, frac)) * 100)}
            className="h-1.5 w-[130px] overflow-hidden rounded-full bg-fill"
          >
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-[var(--dur)] ease-out"
              style={{ width: `${Math.max(0, Math.min(1, frac)) * 100}%` }}
            />
          </div>
        ) : null}

        {busy || done || fail !== "" ? (
          <span className={cn("flex items-center gap-2 font-sans text-sm font-medium", tone)}>
            {/* Точка красится тем же цветом, что и слово рядом: одно правило на
                оба вместо двух ветвлений. Мигание гасим тем, кто просил не
                двигать лишнего - системную галочку уважаем везде. */}
            <span
              aria-hidden="true"
              className={cn(
                "size-2 shrink-0 rounded-full bg-current",
                busy && "animate-pulse motion-reduce:animate-none",
              )}
            />
            {busy
              ? t("меряю")
              : fail !== ""
                ? t("не вышло")
                : ok
                  ? t("быстрее")
                  : t("не помогло")}
          </span>
        ) : null}

        {can && !busy ? (
          // «Проверить», а не «Ускорить»: ускорит или нет - решает замер, и
          // обещать в подписи то, чего может не случиться, нельзя.
          <Button
            kind="primary"
            label={done || fail !== "" ? t("Ещё раз") : t("Проверить")}
            onClick={() => {
              setFail("");
              setDone(false);
              setBusy(true);
              setStage("");
              setFrac(0);
              void dmlRun();
            }}
          />
        ) : null}
      </div>
    </SettingRow>
  );
}
