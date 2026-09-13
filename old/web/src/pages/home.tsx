// Страница «Главная».
//
// Канон Korti (templates/app-shell, Overview): крупный заголовок, ряд карточек-
// метрик, ниже список последних событий. Здесь то же самое, только события -
// ваши диктовки. Страница отвечает на три вопроса и больше ни на что: работает?
// что сделала? сколько всего?
//
// **Захват сочетания остаётся в Python, и это не временное положение дел.**
// Браузеру клавишу Win не отдают вовсе, половина сочетаний уходит системе или
// окну раньше, чем событие дойдёт до страницы, а боковых кнопок мыши у
// клавиатурных событий нет совсем. Плюс имена клавиш обязаны совпадать с теми,
// которыми приложение вешает хоткей: разойдись поле и хук в понимании слова
// «ctrl» - и получится баг, который здесь уже был. Поэтому страница только
// просит начать (startCapture) и ждёт результат сигналом captureDone; ловит
// нажатия хук keyboard на стороне Python (Backend.startCapture).
import { useEffect, useState } from "react";

import {
  acceptSuggestion,
  ago,
  cancelCapture,
  copyText,
  declineSuggestion,
  getSetting,
  homeData,
  llmBusy,
  llmInstall,
  llmState,
  on,
  pretty,
  startCapture,
  statusInfo,
  suggestions,
} from "../bridge/api";
import { call } from "../bridge/client";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { KeyCaps } from "../ui/chart/key-caps";
import { Metric } from "../ui/chart/metric";
import { cn } from "../ui/cn";
import { FlowInput } from "../ui/form/input";
import { Icon } from "../ui/icons";
import { HotkeyField } from "../ui/misc/hotkey-field";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";

/** Одна диктовка из истории. */
interface Row {
  text: string;
  ts: string;
}

/** Числа для ряда метрик - то, что считает stats.py. */
interface Stats {
  saved_sec?: string;
  speed?: string;
  speedOk?: boolean;
  words?: string;
}

/** Строка состояния: готов ли, чем распознаёт, на чём считает. */
interface Status {
  ready?: boolean;
  model?: string;
  device?: string;
}

/** Что программа заметила в истории и предлагает превратить в фразу. */
interface Tip {
  value: string;
  kind: string;
  /** «4 раза» - согласование числительного считает Python, а не мы. */
  times: string;
}

// Первые ~80 знаков - столько помещается в карточку двумя строками. Режем по
// границе слова: «сводку по прод…» человек дочитывает сам, а «сводку по прода»
// выглядит как обрыв связи. Порог 50 - чтобы длинное слово без пробелов не
// съело полстроки.
function preview(s: string): string {
  if (!s) return "";
  if (s.length <= 80) return s;
  const cut = s.slice(0, 80);
  const sp = cut.lastIndexOf(" ");
  return (sp > 50 ? cut.slice(0, sp) : cut) + "…";
}

export function HomePage() {
  const [greeting, setGreeting] = useState(t("Главная"));
  const [st, setSt] = useState<Stats>({});
  const [recent, setRecent] = useState<Row[]>([]);
  const [status, setStatus] = useState<Status>({});
  const [tips, setTips] = useState<Tip[]>([]);

  // Чем диктовать. «Зажать» главнее: это основной жест, и мастер первого
  // запуска настраивает именно его.
  const [holdMode, setHoldMode] = useState(false);
  /** Сочетание, которым диктуют, - человекочитаемым. Пусто - не назначено. */
  const [combo, setCombo] = useState("");
  /** Отдельно только «зажать»: им заряжено поле захвата на этой странице. */
  const [holdCombo, setHoldCombo] = useState("");
  const [capturing, setCapturing] = useState(false);

  const [lastAgo, setLastAgo] = useState("");

  // Последняя диктовка отделена от остальных намеренно. Страница отвечает на
  // «оно работает и что оно только что сделало?», и ответ на вторую половину
  // вопроса - ровно одна запись. В ровном списке из пяти одинаковых строк она
  // ничем не выделялась и читалась пятой по счёту.
  const last = recent.length > 0 ? recent[0] : null;
  const rest = recent.slice(1);
  // Есть ли что показывать в числах. Пустые метрики (три «0» и прочерк) -
  // худшее первое впечатление, поэтому до первой диктовки ряда чисел нет вовсе,
  // только зов попробовать.
  const hasData = recent.length > 0;

  async function reload() {
    // Одним заходом: числа и последние диктовки живут в одном файле, и читать
    // его дважды незачем.
    const d = (await homeData()) as { stats?: Stats; recent?: Row[] };
    setSt(d?.stats ?? {});
    setRecent(d?.recent ?? []);

    // По имени, а не «Главная». Владелец сказал прямо: «Роман, с возвращением».
    // Имя берём из учётной записи Windows - спрашивать его отдельным экраном
    // ради одной строки не стоит. Не узнали - здороваемся без имени: «Доброе
    // утро, » с пустотой на конце хуже, чем просто «Доброе утро».
    //
    // userName - это Q_PROPERTY, а не @Slot, поэтому обёртки в api.ts у него
    // нет; свойства мост отдаёт тем же `call` без аргументов (bridge.py).
    const h = new Date().getHours();
    // t() на каждой ветке, а не одним вызовом снаружи: иначе строки не видны
    // ни человеку, читающему код, ни tools/check_web_i18n.py - он ищет литерал
    // прямо в скобках t(), и вычислять за нас, что попадёт внутрь, не станет.
    const hi =
      h < 5
        ? t("Доброй ночи")
        : h < 12
          ? t("Доброе утро")
          : h < 18
            ? t("Добрый день")
            : t("Добрый вечер");
    const name = String((await call("userName")) ?? "");
    setGreeting(name ? hi + ", " + name : hi);
  }

  async function refreshTips() {
    setTips(((await suggestions()) as Tip[] | null) ?? []);
  }

  // Строка состояния и сочетание. Спрашиваем приложение (statusInfo), а не свой
  // конфиг: модель меняют на «Дополнительно», а грузится она в приложении.
  async function reloadStatus() {
    setStatus(((await statusInfo()) as Status | null) ?? {});
    await reloadHotkey();
  }

  async function reloadHotkey() {
    const hold = String((await getSetting("hotkey_hold")) ?? "");
    const toggle = String((await getSetting("hotkey_toggle")) ?? "");
    setHoldMode(Boolean(hold));
    setHoldCombo(hold ? String(await pretty(hold)) : "");
    // Проверяем сырые значения, а не pretty(): у пустого сочетания pretty()
    // возвращает «не задано» - непустую строку, и условие на ней всегда истинно.
    // Ровно на этом карточка раньше писала «Зажмите не задано и говорите».
    const spec = hold || toggle;
    setCombo(spec ? String(await pretty(spec)) : "");
  }

  useEffect(() => {
    void reload();
    void refreshTips();
    void reloadStatus();
    // Конфиг меняют и другие страницы, и само приложение: без подписки строка
    // состояния врала бы до следующего открытия окна.
    return on("changed", () => {
      void reload();
      void reloadStatus();
    });
  }, []);

  // Результат захвата приезжает сюда, а не в поле: поле только показывает.
  // Чужие поля отсеиваем по имени - captureDone общий на все восемь сочетаний
  // программы, и «Диктовка» слушает его же.
  useEffect(() => {
    return on("captureDone", (field) => {
      if (field !== "hotkey_hold") return;
      setCapturing(false);
      // Значение уже записано в конфиг самим Backend (_finish), нам остаётся
      // перечитать его тем же путём, что и при открытии страницы: собирать
      // подпись из спецификации своими руками значило бы завести второе мнение
      // о том, как выглядит «ctrl+shift+space».
      void reloadHotkey();
    });
  }, []);

  // «2 минуты назад», а не «14:03». На вопрос «это то, что я только что
  // сказал?» время на часах не отвечает - его ещё надо вычесть из текущего.
  useEffect(() => {
    if (!last) {
      setLastAgo("");
      return;
    }
    void ago(last.ts).then((v) => setLastAgo(String(v ?? "")));
  }, [last]);

  const parts = [t("Готов")];
  // Модель и устройство приходят из приложения и до загрузки модели пусты.
  // Пустой кусок не показываем: «Готов ·  · » хуже, чем «Готов».
  if (status.model) parts.push(t(status.model));
  if (status.device) parts.push(t(status.device));

  return (
    <>
      <Heading level="page">{greeting}</Heading>

      {/* Что программа заметила сама. Страница «Слова» была формой, которую
          надо заполнять руками, - владелец назвал это функцией для айтишника, и
          был прав. Заполнять её теперь предлагает программа: она видит, что
          человек повторяет, и приносит ЗНАЧЕНИЕ. Имя даёт человек - назвать
          по-человечески машина не может, «roman@почта» это «моя почта» или
          «рабочая», знает только он. */}
      {tips.map((tip) => (
        <TipCard key={tip.value} tip={tip} onDone={() => void refreshTips()} />
      ))}

      {/* Первое, что человек должен узнать: работает ли оно и как им
          пользоваться. Не «состояние системы», а строка состояния и одна фраза
          действием. */}
      <Card>
        <div className="flex flex-col gap-3 px-6 pt-4 pb-4">
          {/* «Готов · Обычная · процессор» - три ответа одной строкой: работает
              ли, чем распознаёт, на чём считает. Устройство раньше было видно
              только в журнале, а вопрос «а видеокарту-то оно использует?» задают
              первым. Точка зелёная, а не акцентная: синий в Korti -
              «особенное», а работающая программа это норма. */}
          <p className="flex items-center gap-2 font-sans text-sm font-medium text-text-secondary">
            <span
              aria-hidden="true"
              className={cn(
                "size-2 shrink-0 rounded-full",
                status.ready ? "bg-success" : "bg-text-muted",
              )}
            />
            {status.ready ? parts.join(" · ") : t("Просыпаюсь…")}
          </p>

          {/* Сочетание - крупно и плашками, как в мастере первого запуска. Это
              главное, что человек сюда приходит вспомнить, и строчкой в 12
              пикселей посреди абзаца оно не читалось: глаз ищет на странице
              форму клавиши, а не слово «Ctrl». */}
          {combo ? <KeyCaps combo={combo} /> : null}

          {/* Фраза без названия клавиш: их человек уже прочитал на плашках выше,
              и повторять «Зажмите Ctrl + Shift + Space» значит сказать одно и то
              же дважды подряд. */}
          <p
            className={cn(
              "font-sans text-md leading-[1.3] font-semibold tracking-[-0.2px]",
              combo ? "text-text" : "text-danger",
            )}
          >
            {combo === ""
              ? t("Сочетание не назначено - задайте его на странице «Диктовка».")
              : holdMode
                ? t("Зажмите и говорите. Отпустили - текст на месте.")
                : t("Нажмите и говорите. Нажмите ещё раз - текст на месте.")}
          </p>
          <p className="font-sans text-sm leading-[1.5] text-text-muted">
            {t("Работает в любом окне: письмо, чат, документ. ") +
              t("Голос не покидает этот компьютер.")}
          </p>
        </div>

        {/* Поле захвата - в той же карточке, что и плашки: человек, который
            пришёл сюда вспомнить сочетание, чаще всего и хочет его сменить, а
            не идти за этим на другую страницу. Ряд остаётся тем же, что на
            «Диктовке», - подписи одни и те же намеренно: два разных названия
            одного сочетания в одном окне читаются как две настройки. */}
        <SettingRow
          icon={<Icon name="keyboard" size={20} />}
          title={t("Удерживать и говорить")}
          subtitle={t("Самый простой способ. Можно назначить и боковую кнопку мыши")}
        >
          <HotkeyField
            field="hotkey_hold"
            value={holdCombo}
            capturing={capturing}
            onStartCapture={(field) => {
              setCapturing(true);
              void startCapture(field);
            }}
            onCancelCapture={() => {
              setCapturing(false);
              void cancelCapture();
            }}
          />
        </SettingRow>
      </Card>

      <LlmBanner />

      {/* Последняя диктовка - крупной карточкой, отдельно от списка.
          Это вторая половина вопроса, ради которого окно открывают: «работает -
          и что оно только что сделало?». Ответ на неё лежал первой строкой
          ровного списка из пяти, то есть выглядел ровно так же, как
          позавчерашняя фраза: его приходилось искать глазами вместо того, чтобы
          увидеть. Пусто - не прячем, а зовём попробовать: дырка на её месте
          выглядит как поломка. */}
      <Card>
        <div className="flex flex-col gap-3 px-6 pt-4 pb-4">
          {/* line-clamp-3 - потолок: обрезано по 80 знакам, но длинные слова
              могут дать третью строку. Дальше карточка начнёт съедать экран. */}
          <p
            data-selectable
            className={cn(
              "line-clamp-3 font-sans text-md leading-[1.4] text-text",
              !last && "font-semibold",
            )}
          >
            {last ? preview(last.text) : t("Надиктуйте первую фразу")}
          </p>

          {last ? (
            // Время и кнопка в одной строке: карточка и так крупная, а отдельная
            // строка под каждую отправила бы список за нижний край окна.
            <div className="flex items-center justify-between gap-4">
              <span className="font-sans text-2xs text-text-muted">{lastAgo}</span>
              {/* Копируем целиком, а не обрезанное превью: человек забирает свою
                  фразу, а не то, что поместилось в карточку. */}
              <Button
                label={t("Скопировать")}
                onClick={() => void copyText(last.text)}
              />
            </div>
          ) : (
            // Пусто: сочетание строкой, а не плашками, и без «зажмите» - жест
            // человек прочитал на карточке прямо над этой. Здесь он узнаёт
            // другое: куда денется сказанное.
            <p className="font-sans text-sm leading-[1.5] text-text-muted">
              {combo === ""
                ? t("Сначала задайте сочетание на странице «Диктовка».")
                : combo + t(" - и текст появится здесь.")}
            </p>
          )}
        </div>
      </Card>

      {/* Числа, а не прилагательные - так говорит система. Первым -
          сэкономленное время: единственное число, ради которого человек вообще
          открыл бы эту страницу.

          Сетка с auto-fit, а не ряд: окно тянется от 940 до любого размера, и на
          узком краю карточки должны переноситься, а не худеть до нечитаемого.
          Порог 200 на карточку - при 640 (ширина колонки) это три столбца, при
          более узком будет два. Верхний предел не нужен: метрик всего три, и
          четвёртой колонке взяться неоткуда. */}
      {hasData ? (
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
          <Metric
            order={0}
            label={t("сэкономлено")}
            value={String(st.saved_sec ?? "") || t("0 с")}
            hint={t("по сравнению с печатью руками")}
          />
          <Metric
            order={1}
            label={t("скорость")}
            pending={!st.speedOk}
            value={
              st.speedOk
                ? String(st.speed ?? "")
                : t("Наговорите минуту - посчитаем")
            }
            hint={t("быстрее, чем печатать руками")}
          />
          <Metric
            order={2}
            label={t("надиктовано")}
            // Чистый счётчик слов - его и оживляем: бежит от нуля.
            countTo={Number.parseInt(String(st.words ?? "0"), 10) || 0}
            hint={t("слов за всё время")}
          />
        </div>
      ) : null}

      {/* Заголовка у списка нет, пока в нём никого: «ПОСЛЕДНЕЕ» над пустотой
          (одна диктовка - она вся ушла в карточку выше) выглядит как не
          загрузившийся список. */}
      {rest.length > 0 ? (
        <>
          <Heading>{t("ПОСЛЕДНЕЕ")}</Heading>
          {/* list, а не набор карточек: диктор объявляет «список, 4 элемента» и
              умеет по нему прыгать. В QML это Repeater, и для диктора он
              немой. */}
          <ul className="flex flex-col gap-2">
            {rest.map((r, i) => (
              <li key={`${r.ts}-${i}`}>
                {/* Тень выключена: карточек в списке бывает несколько, и каждая
                    подняла бы свой слой на композитор. */}
                <Card shadow={false}>
                  {/* Настоящая кнопка, а не MouseArea поверх карточки: строку
                      копируют щелчком, и с клавиатуры это должно работать тоже.
                      В QML до неё не добраться табом вовсе. */}
                  <button
                    type="button"
                    onClick={() => void copyText(r.text)}
                    className="group flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left"
                  >
                    <span
                      aria-hidden="true"
                      className="size-[7px] shrink-0 rounded-full bg-success"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 font-sans text-md text-text">
                        {r.text}
                      </span>
                      {/* Подсказка одна на список, а не по штуке на строку:
                          повторённая четыре раза, она перестаёт быть подсказкой
                          и становится шумом. Показываем под курсором и под
                          фокусом - там, где она и нужна. */}
                      <span
                        className={cn(
                          "mt-1 block font-sans text-2xs text-text-muted opacity-0",
                          "transition-opacity duration-[var(--dur-fast)] ease-out",
                          "group-hover:opacity-100 group-focus-visible:opacity-100",
                        )}
                      >
                        {t("нажмите, чтобы скопировать")}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-2xs text-text-muted">
                      {String(r.ts).slice(11, 16)}
                    </span>
                  </button>
                </Card>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

/**
 * Находка: программа заметила, что человек повторяет одно и то же, и предлагает
 * дать этому короткую фразу.
 *
 * Своим компонентом ради поля ввода: имя у каждой находки своё, и держать их
 * пачкой в состоянии страницы значило бы перерисовывать всю «Главную» на каждую
 * букву.
 */
function TipCard({ tip, onDone }: { tip: Tip; onDone: () => void }) {
  const [name, setName] = useState("");

  // Вид находки приезжает из suggest.py по-русски: «почта», «ссылка», «фраза».
  // «Фраза» - вид по умолчанию, и договаривать его незачем: «Вы диктовали это 4
  // раза - фраза» звучит отчётом машины. Сравниваем переведённое с переведённым:
  // t() меняет показ, а не данные, и одна сторона сырая сломала бы условие при
  // английском интерфейсе.
  const kind = t(String(tip.kind ?? ""));
  const kindNote = kind && kind !== t("фраза") ? " - " + kind : "";

  return (
    <Card>
      <div className="flex flex-col gap-3 px-6 pt-4 pb-4">
        <p className="font-sans text-sm font-semibold text-text">
          {t("Вы диктовали это ") + tip.times + kindNote + t(". Дать короткую фразу?")}
        </p>
        <p className="line-clamp-3 font-sans text-sm leading-[1.4] text-text-muted">
          {"«" + tip.value + "»"}
        </p>
        {/* Перенос по словам оставлен: если подписи кнопок вырастут, ряд
            перенесётся сам. Поле в 180, а не во всю строку, - рядом помещаются
            обе кнопки, и решение занимает одну строку вместо двух. */}
        <div className="flex flex-wrap items-center gap-2">
          <FlowInput
            value={name}
            onChange={setName}
            placeholder={t("как это называть")}
            label={t("как это называть")}
            className="w-[180px]"
          />
          <Button
            kind="primary"
            label={t("Запомнить")}
            onClick={async () => {
              await acceptSuggestion(name, tip.value);
              onDone();
            }}
          />
          <Button
            label={t("Не надо")}
            onClick={async () => {
              await declineSuggestion(tip.value);
              onDone();
            }}
          />
        </div>
      </div>
    </Card>
  );
}

/**
 * Правка текста не установлена - говорим об этом первым делом и не даём об этом
 * забыть.
 *
 * Раньше она была необязательной, и без неё программа просто работала чуть
 * скромнее. Теперь без неё программа неполна: не работают ни поправки на ходу,
 * ни преобразования выделенного текста. Молчать про это значит отдать человеку
 * половину программы и не сказать, что вторая половина существует.
 *
 * ---- Почему состояний три, а не «есть / нет» ----
 *
 * Плашка спрашивала llmReady() и на любое «нет» писала «не установлена», а
 * кнопкой предлагала скачать 3.3 ГБ. Для установленной, но уснувшей Ollama это
 * враньё: она лежит на диске, просто не отвечает, - и человек качал бы три
 * гигабайта поверх трёх имеющихся, чтобы получить то же самое. Кнопка при этом
 * одна на все три случая: ollama_setup.ensure() сам смотрит, чего не хватает.
 * Меняется только подпись, потому что человеку важно знать, на что он
 * соглашается.
 */
function LlmBanner() {
  const [state, setState] = useState("ready");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const load = () => {
      void llmState().then((v) => setState(String(v ?? "")));
      void llmBusy().then((v) => setBusy(Boolean(v)));
    };
    load();
    const offChanged = on("changed", load);
    // Конец установки конфиг не трогает, значит changed не придёт: без этого
    // плашка висела бы с кнопкой «Ставится…» до следующего открытия окна.
    const offDone = on("llmDone", () => {
      void llmState().then((v) => setState(String(v ?? "")));
      setBusy(false);
    });
    return () => {
      offChanged();
      offDone();
    };
  }, []);

  if (state === "ready") return null;

  return (
    <Card>
      <SettingRow
        first
        // Тот же знак, что у «Правки текста» в настройках.
        icon={<Icon name="sparkles" size={20} />}
        title={
          state === "sleeping"
            ? t("Правка текста не отвечает")
            : state === "no_model"
              ? t("Правке текста не хватает модели")
              : t("Правка текста не установлена")
        }
        // Короче, чем разрешённые 60 знаков, и намеренно: справа в этой же
        // строке стоит «подробнее», и на подпись остаётся не вся ширина ряда.
        subtitle={
          state === "sleeping"
            ? t("Установлена, но сейчас не запущена")
            : state === "no_model"
              ? t("Осталось скачать модель")
              : t("Нужна для преобразований текста")
        }
        more={
          t("Без неё не работают преобразования текста и правка ") +
          t("выделенного голосом. Знаки препинания и оговорки ") +
          t("программа чинит сама, без неё. Ставится один раз, ") +
          t("дальше работает без интернета.")
        }
      >
        {/* «Запустить», а не «Переустановить»: переустановка уснувшую Ollama
            тоже вылечит, но ценой трёх гигабайт трафика ради того, что чинится
            запуском сервера за пару секунд. */}
        <Button
          kind="primary"
          disabled={busy}
          label={
            busy
              ? t("Ставится…")
              : state === "sleeping"
                ? t("Запустить")
                : state === "no_model"
                  ? t("Догрузить")
                  : t("Установить")
          }
          onClick={() => {
            setBusy(true);
            void llmInstall();
          }}
        />
      </SettingRow>
    </Card>
  );
}
