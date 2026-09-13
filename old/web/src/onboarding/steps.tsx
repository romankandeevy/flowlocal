// Экраны мастера первого запуска - девять штук, по одному на шаг.
//
// Каркас (шаги, кнопки, слежка за живым нажатием) живёт в wizard.tsx, здесь
// только содержимое. Разделение не косметическое: у экрана главного жеста и у
// экрана второго жеста один общий хук на настоящее нажатие, и хозяин у него
// обязан быть ровно один - разбор в wizard.tsx, syncWatch.
//
// Правило этого файла то же, что было в QML: на каждом экране человеку есть
// что СДЕЛАТЬ, и на это что-то отвечает. Программа про «нажал - сказал -
// готово», и мастер, который рассказывает о ней неподвижным текстом, обещает
// не то, что дальше будет.
//
// **Экраны нарисованы все сразу и прячутся классом, а не размонтируются.**
// Человек, ушедший «Назад» и вернувшийся, находит распознанный текст, результат
// проверки вставки и ход установки на месте - ровно как в QML, где шаги стояли
// в дереве и переключались свойством visible. Прятать надо именно классом
// display:none: он заодно убирает спрятанное из обхода табом, а «скрытый» экран,
// по которому ходит фокус, - это восемь невидимых остановок между кнопками.
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  cancelCapture,
  getSetting,
  llmInstall,
  micOptions,
  on,
  setSetting,
  startCapture,
  starterMb,
  testInsert,
  themeSwatch,
  trialStart,
  trialStop,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { KeyCaps } from "../ui/chart/key-caps";
import { cn } from "../ui/cn";
import { FlowInput } from "../ui/form/input";
import { Segmented } from "../ui/form/segmented";
import { Select } from "../ui/form/select";
import { ToggleRow } from "../ui/form/toggle";
import { Icon } from "../ui/icons";
import { LayoutModeProvider, type LayoutMode } from "../ui/layout-mode";
import { HotkeyField } from "../ui/misc/hotkey-field";
import { Wordmark } from "../ui/misc/nav";
import { Heading } from "../ui/text";
import { MicWave } from "./mic-wave";

/** Живое нажатие одного сочетания. */
export interface Combo {
  /** Запись из конфига - «ctrl+shift+space». */
  spec: string;
  /** Она же по-человечески, от inputspec.pretty. */
  pretty: string;
  /** Какие плашки зажаты прямо сейчас, по индексу. */
  down: boolean[];
  /** Сочетание собрано целиком. */
  lit: boolean;
  /** Жест доказан живьём хотя бы раз. Латч: он и отпирает «Дальше». */
  verified: boolean;
}

/** Что мастер знает про модель распознавания. */
export interface ModelState {
  chosen: string;
  /** На месте ОБЕ модели - русская и английская. */
  ready: boolean;
  downloading: boolean;
  frac: number;
}

/** Всё, что каркас держит за экраны: они рисуют, состояние живёт в одном месте. */
export interface Wiz {
  step: number;
  model: ModelState;
  hold: Combo;
  /** У второго жеста есть ещё и осознанный отказ. */
  toggle: Combo & { skipped: boolean };
  /** «Мне хватит одного жеста»: снять требование и уйти вперёд. */
  onSkipToggle: () => void;
  /** Закрыть мастер. Python сам запишет onboarded и погасит окно. */
  onFinish: () => void;
}

/**
 * Проявление через переход, без своих @keyframes.
 *
 * CSS-переход не срабатывает, если элемент родился уже в конечном состоянии, -
 * ему нужно, чтобы значение поменялось на живом элементе. Отсюда кадр
 * ожидания: рисуем спрятанным и снимаем это на следующем кадре. Кадра ровно
 * два, и второй не лишний: один браузер имеет право склеить с первой отрисовкой,
 * и тогда перехода не будет вовсе - будет мгновенная подстановка.
 */
function useAppear(trigger: unknown): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    setShown(false);
    let inner = 0;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => setShown(true));
    });
    return () => {
      cancelAnimationFrame(outer);
      cancelAnimationFrame(inner);
    };
  }, [trigger]);
  return shown;
}

export function Steps({ wiz }: { wiz: Wiz }) {
  const shown = useAppear(wiz.step);
  // Откуда пришли: вперёд содержимое въезжает справа, назад - слева. Само по
  // себе движение маленькое, но без него «Назад» и «Дальше» выглядят
  // одинаково, и человек теряет, в какую сторону он идёт.
  const prev = useRef(wiz.step);
  const from = wiz.step >= prev.current ? 8 : -8;
  useEffect(() => {
    prev.current = wiz.step;
  }, [wiz.step]);

  return (
    <div
      className="transition-[opacity,transform] duration-[var(--dur)] ease-out"
      style={{
        opacity: shown ? 1 : 0,
        transform: `translateX(${shown ? 0 : from}px)`,
      }}
    >
      <Screen on={wiz.step === 0}>
        <HelloStep />
      </Screen>
      <Screen on={wiz.step === 1}>
        <LookStep />
      </Screen>
      <Screen on={wiz.step === 2}>
        <ModelStep model={wiz.model} />
      </Screen>
      <Screen on={wiz.step === 3}>
        <MicStep on={wiz.step === 3} />
      </Screen>
      <Screen on={wiz.step === 4}>
        <HoldStep combo={wiz.hold} />
      </Screen>
      <Screen on={wiz.step === 5}>
        <ToggleStep combo={wiz.toggle} onSkip={wiz.onSkipToggle} />
      </Screen>
      <Screen on={wiz.step === 6}>
        <InsertStep />
      </Screen>
      <Screen on={wiz.step === 7}>
        <TrialStep on={wiz.step === 7} />
      </Screen>
      <Screen on={wiz.step === 8}>
        <LlmStep onFinish={wiz.onFinish} />
      </Screen>
    </div>
  );
}

function Screen({ on: visible, children }: { on: boolean; children: ReactNode }) {
  return <div className={visible ? undefined : "hidden"}>{children}</div>;
}

/**
 * Заголовок шага.
 *
 * Свой, а не Heading level="page": в мастере он на ступень мельче (20 против
 * 26), окно у мастера 640 в ширину, и дисплейный кегль забирал бы под себя
 * треть экрана. Тег тот же, h1: диктор обязан называть шаг заголовком, и это
 * прямое требование - в QML-версии все заголовки Text, то есть для него их нет.
 */
function StepTitle({ children }: { children: ReactNode }) {
  return <h1 className="font-sans text-xl font-semibold text-text">{children}</h1>;
}

/** Пояснение под заголовком шага - тише текста, во всю ширину. */
function StepNote({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p className={cn("w-full font-sans text-sm text-text-muted", className)}>
      {children}
    </p>
  );
}

// ---------- 0. Привет ----------

function HelloStep() {
  return (
    <div className="flex flex-col items-center gap-6 py-6">
      {/* Знак, а не голое имя: это первое, что человек видит от программы, и
          стена текста на белом - плохое первое впечатление для приложения,
          которое дальше показывает себя аккуратным.

          И он отзывается на касание: наводка приподнимает знак, нажатие - кивок,
          тот же, которым пилюля говорит «готово». На этом экране трогать больше
          нечего, кроме одной кнопки, а первое, к чему тянется мышь, - самое
          крупное на экране. Пусть отвечает: программа про отклик, и говорить об
          этом надо с первого экрана. */}
      <div className="transition-transform duration-[var(--dur)] ease-out hover:scale-[1.02] active:scale-[0.96]">
        <Wordmark size="lg" />
      </div>

      <div className="flex w-full flex-col items-center gap-4">
        {/* Обещание в три коротких такта, ритмом из README: коротко, действием,
            без восклицаний. */}
        <Heading level="page" className="text-center">
          {t("Зажали. Сказали. Отпустили.")}
        </Heading>
        {/* Под обещанием, тише: куда денется текст. Это подсказка, а не второй
            заголовок, отсюда вторичный цвет и основной кегль. */}
        <p className="text-center font-sans text-md text-text-secondary">
          {t("Текст уже в том окне, где курсор")}
        </p>
      </div>

      {/* Приватность - тише всех: мелко и спокойно, отдельной строкой на
          расстоянии. Обещание вполголоса, ему не нужен ни кегль, ни цвет
          заголовка - только чтобы его прочли и пошли дальше. */}
      <p className="max-w-[420px] text-center font-sans text-sm leading-[1.35] text-text-muted">
        {t("Звук и текст не покидают этот компьютер.")}
      </p>
    </div>
  );
}

// ---------- 1. Как это выглядит ----------

/** Краски конкретной темы - их считает Python, см. onboarding_qt.themeSwatch. */
interface Swatch {
  paper: string;
  ink: string;
  text: string;
  textMuted: string;
  textFaint: string;
  border: string;
  fillStrong: string;
  accent: string;
  accentFg: string;
  success: string;
}

// Вторым экраном намеренно: дальше человек проходит ещё семь шагов и видит их
// уже в своём оформлении. Спросить об этом в конце значило бы показать мастер
// дважды - один раз чужим, один раз своим.
function LookStep() {
  // sub - подпись только у «Системы»: она показывает не свой фиксированный
  // цвет, а тот, что стоит в Windows.
  const cards = [
    { value: "system", name: t("Система"), sub: t("как в Windows") },
    { value: "light", name: t("Светлая"), sub: "" },
    { value: "dark", name: t("Тёмная"), sub: "" },
  ];

  const [theme, setTheme] = useState("system");
  const [layout, setLayout] = useState<LayoutMode>("cards");
  const [swatches, setSwatches] = useState<Record<string, Swatch>>({});
  const [demoOne, setDemoOne] = useState(true);
  const [demoTwo, setDemoTwo] = useState(false);

  useEffect(() => {
    void getSetting("theme").then((v) => setTheme(String(v || "system")));
    void getSetting("layout").then((v) =>
      setLayout(String(v || "cards") === "lines" ? "lines" : "cards"),
    );
  }, []);

  // Краски каждой темы считает Python один раз и от текущей темы не зависят:
  // светлая карточка обязана остаться светлой рядом с тёмной. Взять их из
  // токенов страницы нельзя - там живёт ТЕКУЩАЯ тема, и все три карточки
  // показали бы одно и то же.
  useEffect(() => {
    let alive = true;
    const names = ["system", "light", "dark"];
    void Promise.all(names.map((n) => themeSwatch(n))).then((list) => {
      if (!alive) return;
      const out: Record<string, Swatch> = {};
      names.forEach((n, i) => {
        const sw = list[i];
        // Ключи гарантирует Python: словарь собран там поимённо, а не собран
        // из чего попало.
        if (sw) out[n] = sw as unknown as Swatch;
      });
      setSwatches(out);
    });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <StepTitle>{t("Как вам удобнее?")}</StepTitle>
      <StepNote>{t("Это можно поменять когда угодно, в настройках.")}</StepNote>

      <Heading level="section">{t("ЦВЕТА")}</Heading>

      {/* Выбор темы блоками-превью, а не переключателем: слово «тёмная» ничего
          не показывает, пока человек не увидел тёмную. */}
      <div className="grid grid-cols-3 gap-2.5">
        {cards.map((card) => (
          <ThemeCard
            key={card.value}
            name={card.name}
            sub={card.sub}
            swatch={swatches[card.value]}
            selected={theme === card.value}
            onPick={() => {
              setTheme(card.value);
              setSetting("theme", card.value);
            }}
          />
        ))}
      </div>

      {/* Было «РАСПОЛОЖЕНИЕ: карточками / строками». Владелец спросил
          «расположение чего?» - и правильно спросил: ничего никуда не
          переставляется, меняется только фон под настройками. Так же
          называется и в самих настройках, одними словами. */}
      <Heading level="section">{t("ФОН ПОД НАСТРОЙКАМИ")}</Heading>
      <div>
        <Segmented
          value={layout}
          label={t("ФОН ПОД НАСТРОЙКАМИ")}
          onChange={(v) => {
            setLayout(v);
            setSetting("layout", v);
          }}
          options={[
            { label: t("есть"), value: "cards" as LayoutMode },
            { label: t("нет"), value: "lines" as LayoutMode },
          ]}
        />
      </div>

      {/* Показываем разницу тут же, а не описываем словами: «с фоном» и «без
          фона» человеку ничего не говорят, пока он их не увидел. И подписываем,
          что это образец: раньше здесь просто стояли две настройки, и владелец
          спросил, зачем этот блок вообще нужен - он выглядел как настоящие
          настройки, которые почему-то ничего не делают. */}
      <StepNote>
        {t(
          "Образец - чтобы увидеть разницу. Эти два переключателя ни на что не влияют:",
        )}
      </StepNote>
      {/* Образец обязан слушаться выбранного фона, поэтому у него своя
          раскладка: окно мастера общей ещё не имеет, а именно разницу между
          «есть» и «нет» человек сюда и смотрит. */}
      <LayoutModeProvider mode={layout}>
        <Card>
          {/* Живой, а не мёртвый: неподвижный образец не показывает главного -
              что переключение ВИДНО. Ровно этого владелец и не увидел в тёмной
              теме. */}
          <ToggleRow
            first
            title={t("Так выглядит настройка")}
            subtitle={t("А так - пояснение под ней")}
            checked={demoOne}
            onChange={setDemoOne}
          />
          <ToggleRow
            title={t("И следующая за ней")}
            subtitle={t("Разделены линией в обоих видах")}
            checked={demoTwo}
            onChange={setDemoTwo}
          />
        </Card>
      </LayoutModeProvider>
    </div>
  );
}

/**
 * Одна карточка выбора темы: мини-окно в красках СВОЕЙ темы.
 *
 * Краски идут разметкой, а не классами, и это единственное место, где так
 * можно: токены описывают текущую тему, а карточка обязана показать другую.
 * Числа при этом честные - их считает theme.py, тот же источник правды.
 *
 * Кнопка с aria-pressed, а не радиогруппа: у радиогруппы своя ходьба стрелками,
 * и ради трёх картинок писать её заново незачем - «выбрано/не выбрано» диктор
 * называет и так.
 */
function ThemeCard({
  name,
  sub,
  swatch,
  selected,
  onPick,
}: {
  name: string;
  sub: string;
  swatch?: Swatch;
  selected: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onPick}
      className="flex cursor-pointer flex-col gap-2"
    >
      {/* Рамка всегда в два пикселя, меняется только краска. В QML она росла с
          1 до 2 и уводила содержимое на пиксель - на трёх карточках подряд
          этот скачок читается как дрожь. */}
      <div
        className={cn(
          "h-[106px] w-full overflow-hidden rounded-[10px] border-2 p-1.5",
          "transition-colors duration-[var(--dur-fast)] ease-out",
          selected ? "border-accent" : "border-border",
        )}
      >
        {swatch ? (
          <div
            className="flex h-full w-full flex-col gap-2.5 rounded-sm border p-2.5"
            style={{ backgroundColor: swatch.paper, borderColor: swatch.border }}
          >
            {/* Строка настройки: два «текста» слева, переключатель справа.
                Ровно то, что стоит в образце ниже, только в миниатюре. */}
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <div
                  className="h-[5px] w-11 rounded-full"
                  style={{ backgroundColor: swatch.text }}
                />
                <div
                  className="h-1 w-7 rounded-full"
                  style={{ backgroundColor: swatch.textMuted }}
                />
              </div>
              {/* Переключатель включён: дорожка - чернила (в системе «включено»
                  это чернила, не акцент), ручка - бумага. */}
              <div
                className="flex h-[13px] w-[22px] items-center justify-end rounded-full px-0.5"
                style={{ backgroundColor: swatch.ink }}
              >
                <div
                  className="size-[9px] rounded-full"
                  style={{ backgroundColor: swatch.paper }}
                />
              </div>
            </div>

            <div className="h-px w-full" style={{ backgroundColor: swatch.border }} />

            {/* Акцентная кнопка с «подписью» внутри. */}
            <div
              className="flex h-[18px] w-full items-center justify-center rounded-sm"
              style={{ backgroundColor: swatch.accent }}
            >
              <div
                className="h-[5px] w-8 rounded-full"
                style={{ backgroundColor: swatch.accentFg }}
              />
            </div>
          </div>
        ) : null}
      </div>

      <span className="flex flex-col items-center gap-px">
        <span
          className={cn(
            "font-sans text-sm transition-colors duration-[var(--dur-fast)] ease-out",
            selected ? "font-semibold text-text" : "font-medium text-text-secondary",
          )}
        >
          {name}
        </span>
        {sub ? <span className="font-sans text-2xs text-text-faint">{sub}</span> : null}
      </span>
    </button>
  );
}

// ---------- 2. Модель ----------
//
// Выбора модели на этом шаге нет. Был выбор языка - «русский» против «русский и
// другие», - и за ним стояли две разные модели. Многоязычных моделей в каталоге
// не осталось: программа про русский, и выбирать не из чего, а выбор, где
// вариант один, - это не выбор, а лишний экран.
//
// Шаг остался, потому что делает главное: качает модель. Без неё диктовка не
// работает вовсе, и человек должен видеть, что качается и сколько осталось.

function ModelStep({ model }: { model: ModelState }) {
  const [mb, setMb] = useState(0);
  const done = useAppear(model.ready);

  // Цену называем ДО скачивания, а не после, - тем же приёмом, что на экране
  // правки текста («Скачаем 3.3 ГБ»). Число берём у Python: оно складывается из
  // двух моделей и разъедется с правдой в первый же день, если держать его
  // строкой в вёрстке.
  useEffect(() => {
    void starterMb().then((v) => setMb(Number(v) || 0));
  }, []);

  // Экран был пустым: заголовок, одна строка про мегабайты - и всё. Владелец
  // назвал это абсурдом, и он прав: человека просят подождать несколько минут и
  // ничего не говорят о том, чего он ждёт. Четыре строки отвечают на настоящие
  // вопросы: сколько ждать, что будет потом и не уедет ли что-нибудь наружу.
  const bullets = [
    {
      title: `${mb}${t(" МБ, три-пять минут")}`,
      sub: t("Скачивается один раз. Дальше не понадобится"),
    },
    {
      title: t("Русский и английский"),
      sub: t("Скажете фразу по-английски - она так и запишется, буквами"),
    },
    {
      title: t("Дальше - без интернета"),
      sub: t("Распознавание идёт на этом компьютере, в самолёте и на даче тоже"),
    },
    {
      title: t("Видеокарта не нужна"),
      sub: t("Хватает обычного процессора: 8 секунд речи - меньше секунды работы"),
    },
  ];

  const pct = Math.round(Math.max(0, Math.min(1, model.frac)) * 100);

  return (
    <div className="flex flex-col gap-3">
      <StepTitle>
        {model.ready ? t("Модель на месте") : t("Скачаем модель")}
      </StepTitle>
      <StepNote className="leading-[1.4]">
        {model.ready
          ? t("Всё уже на этом компьютере. Дальше интернет для распознавания не нужен.")
          : t("Это то, что превращает вашу речь в текст. Она работает прямо ") +
            t("здесь, поэтому её надо принести целиком - один раз.")}
      </StepNote>

      {!model.ready ? (
        <ul className="mt-1 flex flex-col gap-2">
          {bullets.map((b) => (
            <li key={b.title} className="flex gap-3">
              <span
                aria-hidden="true"
                className="mt-[7px] size-[5px] shrink-0 rounded-full bg-text-faint"
              />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="font-sans text-sm font-medium text-text">
                  {b.title}
                </span>
                <span className="font-sans text-sm text-text-muted">{b.sub}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {/* Прогресс скачивания: полоса плюс проценты словами. Без числа полоса на
          трёхстах мегабайтах выглядит замершей - «зависло», сказал владелец, и
          по одной полосе отличить это было невозможно. Полоса одна на обе
          модели: качаются они подряд, а человеку это одно ожидание, а не два. */}
      {model.downloading ? (
        <div className="mt-1 flex flex-col gap-2">
          <div
            role="progressbar"
            aria-label={t("Скачаем модель")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            className="h-1 w-full overflow-hidden rounded-full bg-fill-strong"
          >
            {/* Полоса догоняет самым долгим сроком системы: проценты приходят
                редкими скачками, и рывок на них читается как подвисание. */}
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-[var(--dur-slow)] ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="font-sans text-sm text-text-muted">
            {pct + t("% · качается, можно не смотреть")}
          </p>
        </div>
      ) : null}

      {/* Конец скачивания - единственный момент этого экрана, которого человек
          действительно ждёт, и раньше он проходил молча: полоса исчезала,
          строка появлялась. Теперь галка проявляется тем же кивком, каким
          пилюля говорит «готово», - ответ на пять минут ожидания должен быть
          виден. */}
      {model.ready ? (
        <div
          className="flex items-center gap-2 transition-[opacity,transform] duration-[var(--dur-slow)] ease-out"
          style={{ opacity: done ? 1 : 0, transform: `scale(${done ? 1 : 0.96})` }}
        >
          <Icon name="check" size={16} strokeWidth={2.2} className="text-success" />
          <span className="font-sans text-sm text-success">
            {t("Уже скачано - можно дальше.")}
          </span>
        </div>
      ) : null}
    </div>
  );
}

// ---------- 3. Микрофон ----------
//
// Волна тут в полтора раза выше остальных и занимает почти весь экран под
// выбором устройства. Это не украшение: единственный экран мастера, который
// отвечает на голос, и главный живой момент всего знакомства. Мелкая волна под
// абзацем текста читалась как индикатор, а она - доказательство, что программа
// слышит.

/** Пункт списка от Backend: значение бывает и числом, и пустым. */
interface RawOption {
  label: string;
  value: unknown;
}

/**
 * Имя для «микрофона по умолчанию».
 *
 * В конфиге это пустое значение, а Radix на пустую строку ругается отдельно -
 * у него она означает «ничего не выбрано». Поэтому внутри списка умолчание
 * ездит под именем, а в конфиг уходит ровно то, что прислал Python: подменять
 * его числом или строкой значило бы завести второе мнение о типе настройки.
 */
const MIC_DEFAULT = "default";

function micKey(v: unknown): string {
  return v === null || v === undefined || v === "" ? MIC_DEFAULT : String(v);
}

function MicStep({ on: visible }: { on: boolean }) {
  const [options, setOptions] = useState<RawOption[]>([]);
  const [device, setDevice] = useState("");
  const [heard, setHeard] = useState(false);

  useEffect(() => {
    // Список берём у Backend, а не собираем сами: один физический микрофон
    // PortAudio показывает по разу на каждый host-api, и подписи там уже
    // разведены («Микрофон (Realtek) · MME»).
    void micOptions().then((v) => setOptions((v as RawOption[]) ?? []));
    void getSetting("mic_device").then((v) => setDevice(micKey(v)));
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{t("Микрофон")}</StepTitle>
      <StepNote>
        {t(
          "Скажите что-нибудь - волна должна ожить. Если лежит ровно, выберите другой микрофон.",
        )}
      </StepNote>

      <div>
        <Select
          value={device}
          label={t("Микрофон")}
          options={options.map((o) => ({ label: o.label, value: micKey(o.value) }))}
          onChange={(key) => {
            setDevice(key);
            const found = options.find((o) => micKey(o.value) === key);
            setSetting("mic_device", found ? found.value : null);
          }}
        />
      </div>

      {/* Живая волна - чернила, как в оверлее: данные, а не статус. */}
      <div className="flex h-[132px] w-full items-center justify-center rounded-lg border border-border bg-paper">
        <MicWave running={visible} bars={40} barWidth={5} gap={3} maxHeight={96} onHeard={setHeard} />
      </div>

      {/* Слово к волне. Форму волны человек видит, но вывод из неё делает не
          сразу: «ровно» и «чуть шевелится» на глаз похожи, а решение на этом
          экране принимается одно - тот микрофон или не тот. */}
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={cn(
            "size-2 shrink-0 rounded-full transition-colors duration-[var(--dur-fast)] ease-out",
            heard ? "bg-success" : "bg-text-faint",
          )}
        />
        <span
          className={cn(
            "font-sans text-sm transition-colors duration-[var(--dur-fast)] ease-out",
            heard ? "text-success" : "text-text-muted",
          )}
        >
          {heard ? t("слышу вас") : t("тихо - скажите что-нибудь")}
        </span>
      </div>
    </div>
  );
}

// ---------- 4 и 5. Жесты ----------

/**
 * Поле смены сочетания.
 *
 * keyStart отключён намеренно: пробел из ctrl+shift+space не должен запускать
 * захват, иначе живая проверка жеста выше дерётся с переназначением - захват
 * шёл по кругу, и «Дальше» не открывалась. Менять клавишу - осознанным кликом.
 *
 * Захват ловит Python: браузеру Win не отдают вовсе, боковых кнопок мыши у
 * клавиатурных событий нет, а имена клавиш обязаны совпасть с теми, которыми
 * приложение вешает хоткей.
 */
function StepHotkey({
  field,
  value,
}: {
  field: "hotkey_hold" | "hotkey_toggle";
  value: string;
}) {
  const [capturing, setCapturing] = useState(false);

  useEffect(
    () =>
      on("captureDone", (which) => {
        if (String(which) === field) setCapturing(false);
      }),
    [field],
  );

  return (
    <HotkeyField
      field={field}
      value={value}
      capturing={capturing}
      keyStart={false}
      onStartCapture={() => {
        setCapturing(true);
        void startCapture(field);
      }}
      onCancelCapture={() => {
        setCapturing(false);
        void cancelCapture();
      }}
    />
  );
}

/** Рамка с плашками и подписью состояния - одна на оба экрана жестов. */
function ComboBox({ combo, hint }: { combo: Combo; hint: string }) {
  const good = combo.lit || combo.verified;
  return (
    <div
      className={cn(
        "flex h-[116px] w-full flex-col justify-center gap-3 rounded-lg border bg-paper px-4",
        "transition-colors duration-[var(--dur-fast)] ease-out",
        // Зелёная и на живом нажатии, и после того как жест уже доказан:
        // рамка-подтверждение не должна гаснуть, стоит отпустить клавиши.
        good ? "border-success" : "border-border",
      )}
    >
      {/* Пустое сочетание - законное состояние: во время захвата Backspace его
          стирает. Плашки тогда не рисуем вовсе, иначе pretty отдал бы «не
          задано», и это встало бы отдельной клавишей. */}
      {combo.spec !== "" ? (
        // Крупнее, чем в главном окне: там сочетание вспоминают мельком, здесь
        // по нему бьют пальцем.
        <KeyCaps combo={combo.pretty} keySize={20} down={combo.down} lit={combo.lit} />
      ) : null}

      <div className="flex gap-1.5">
        {combo.verified ? (
          <Icon
            name="check"
            size={15}
            strokeWidth={2.2}
            className="mt-px shrink-0 text-success"
          />
        ) : null}
        <span
          className={cn(
            "font-sans text-sm transition-colors duration-[var(--dur-fast)] ease-out",
            combo.verified ? "text-success" : "text-text-faint",
          )}
        >
          {hint}
        </span>
      </div>
    </div>
  );
}

// Здесь человеку называют клавиши, которыми он будет пользоваться каждый день,
// - и до сих пор не давали их попробовать: поле захвата отвечало на клик мышью,
// а на само нажатие не отвечало ничем. Теперь плашки живые: зажал Ctrl -
// утонула одна, добавил Shift - вторая, собрал сочетание целиком - загорелись
// все. Проверка идёт тем же движением, каким потом диктуют.
function HoldStep({ combo }: { combo: Combo }) {
  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{t("Главный жест: зажать и говорить")}</StepTitle>
      <StepNote>
        {t(
          "Зажали - говорите, отпустили - вставилось. Нажмите сочетание прямо сейчас - плашки отзовутся.",
        )}
      </StepNote>

      {/* Доказанный жест - галка и зелёное «Работает»: это и есть условие,
          отпершее «Дальше», человек должен видеть, что именно он выполнил. */}
      <ComboBox
        combo={combo}
        hint={
          combo.verified
            ? t("Работает - так и диктуйте")
            : combo.spec === ""
              ? t("Сочетание не назначено - задайте его ниже")
              : t("Зажмите и подержите - проверим, что срабатывает")
        }
      />

      {/* Смена сочетания - вторым действием и с подписью. */}
      <Heading level="section">{t("ПОМЕНЯТЬ")}</Heading>
      <StepHotkey field="hotkey_hold" value={combo.pretty} />
      <p className="w-full font-sans text-2xs text-text-faint">
        {t(
          "Кликните по полю и нажмите своё - подойдёт и боковая кнопка мыши. Дальше настроим второй жест: нажал один раз и говоришь со свободными руками.",
        )}
      </p>
    </div>
  );
}

// Отдельным экраном, а не строкой в настройках: владелец просил не просто
// назвать второй жест, а заставить его ВЫПОЛНИТЬ - иначе человек заводит
// сочетание и не знает, срабатывает ли оно. Разница с главным жестом одна и
// важная: этот необязателен, и на экране есть явный выход - навязывать второе
// сочетание тому, кому хватает первого, нечестно.
function ToggleStep({
  combo,
  onSkip,
}: {
  combo: Combo & { skipped: boolean };
  onSkip: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{t("Второй жест: нажать один раз")}</StepTitle>
      <StepNote>
        {t(
          "Нажали один раз - пошла запись, нажали ещё раз - остановилась. Удобно, когда руки заняты, а сказать надо много.",
        )}
      </StepNote>

      <ComboBox
        combo={combo}
        hint={
          combo.verified
            ? t("Работает - этим и включайте")
            : combo.spec === ""
              ? t("Сочетание не назначено - задайте его ниже")
              : t("Нажмите это сочетание - проверим, что срабатывает")
        }
      />

      <Heading level="section">{t("ПОМЕНЯТЬ")}</Heading>
      <StepHotkey field="hotkey_toggle" value={combo.pretty} />
      <p className="w-full font-sans text-2xs text-text-faint">
        {t(
          "Предложили сочетание, которое есть на любой клавиатуре. Можно оставить, поменять или назначить боковую кнопку мыши.",
        )}
      </p>

      {/* Явный выход. Это не то же, что «Дальше»: «Дальше» ждёт доказанного
          жеста, а эта кнопка честно снимает само требование. */}
      <div className="mt-1">
        <Button label={t("Мне хватит одного жеста")} onClick={onSkip} />
      </div>
    </div>
  );
}

// ---------- 6. Проверим вставку ----------

/** Сколько горит кольцо вокруг поля: 120 мс на проявление плюс 700 стоянки.
 *
 * 700 - ВНЕ трёх токенов, и намеренно. Это не движение, а стоянка: рамка горит
 * неподвижно, пока человек переводит взгляд с кнопки на поле. Токены задают
 * срок перехода, а сколько держать готовый кадр, диктует чтение. На 280 мс
 * вспышку пропускали. */
const FLASH_MS = 820;

function InsertStep() {
  const fieldId = useId();
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [failed, setFailed] = useState(false);
  const [flash, setFlash] = useState(false);
  // Ответ приходит сигналом, а замыкание подписки живёт с первой отрисовки:
  // без зеркала в ref оно вечно видело бы пустое поле и всегда говорило бы
  // «не сработало».
  const textRef = useRef(text);
  textRef.current = text;

  useEffect(
    () =>
      on("insertDone", (ok) => {
        const good = ok === true && textRef.current.length > 0;
        setFailed(!good);
        setResult(
          good
            ? t("Работает.")
            : t(
                "не сработало - проверьте антивирус или включите режим «посимвольно» в настройках",
              ),
        );
        if (good) setFlash(true);
      }),
    [],
  );

  useEffect(() => {
    if (!flash) return;
    const id = window.setTimeout(() => setFlash(false), FLASH_MS);
    return () => window.clearTimeout(id);
  }, [flash]);

  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{t("Проверим вставку")}</StepTitle>
      <StepNote>
        {t(
          "Нажмите кнопку - текст должен появиться в поле. Если не появился, мешает антивирус.",
        )}
      </StepNote>

      {/* Поле в обёртке ради кольца вокруг него. Текст, появившийся сам, легко
          принять за тот, что лежал там всегда: человек нажал кнопку, моргнул - и
          в поле что-то есть. Кольцо на секунду показывает, ЧТО именно сейчас
          произошло и где. */}
      <div className="relative w-full">
        <FlowInput
          id={fieldId}
          value={text}
          onChange={setText}
          label={t("Проверим вставку")}
          placeholder={t("сюда вставится проверочный текст")}
          className="w-full"
        />
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute -inset-[3px] rounded-[9px] border-2 border-success",
            "transition-opacity ease-out",
            // Проявление быстрым сроком, угасание самым долгим: вспышка должна
            // успеть попасться на глаза, а гаснуть ей спешить некуда.
            flash ? "opacity-100 duration-[var(--dur-fast)]" : "opacity-0 duration-[var(--dur-slow)]",
          )}
        />
      </div>

      <div>
        <Button
          label={t("Проверить вставку")}
          kind="primary"
          onClick={() => {
            setText("");
            setResult("");
            setFailed(false);
            // Фокус в поле - настоящий inserter вставляет туда, где курсор.
            const el = document.getElementById(fieldId);
            if (el instanceof HTMLInputElement) el.focus();
            void testInsert();
          }}
        />
      </div>

      {result ? (
        <p
          role="status"
          className={cn("font-sans text-sm", failed ? "text-danger" : "text-success")}
        >
          {result}
        </p>
      ) : null}
    </div>
  );
}

// ---------- 7. Проба ----------
//
// Единственное место, где человек впервые слышит себя от программы. Волна и
// текст стоят в ОДНОЙ рамке намеренно: пока говорят - в ней волна, кончили - в
// ней же проявляется строка. Так видно, что текст сделан из этого голоса, а не
// найден где-то ещё на экране.

function TrialStep({ on: visible }: { on: boolean }) {
  const [rec, setRec] = useState(false);
  const [result, setResult] = useState("");
  // Мгновенная подстановка читается как подмена: распознавание идёт секунду с
  // небольшим, и строка, возникшая рывком, выглядит заранее заготовленной.
  const shown = useAppear(result);

  useEffect(
    () =>
      on("trialReady", (text) => {
        setResult(String(text ?? ""));
        setRec(false);
      }),
    [],
  );

  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{t("Скажите что-нибудь")}</StepTitle>
      <StepNote>{t("Распознанный текст появится здесь и никуда не вставится.")}</StepNote>

      <div>
        <Button
          label={rec ? t("Стоп") : t("Начать запись")}
          kind="primary"
          onClick={() => {
            if (rec) {
              void trialStop();
              setResult(t("распознаю…"));
            } else {
              setResult("");
              void trialStart();
            }
            setRec(!rec);
          }}
        />
      </div>

      <div
        className={cn(
          "flex min-h-[112px] w-full items-center justify-center rounded-lg border bg-paper p-4",
          "transition-colors duration-[var(--dur-fast)] ease-out",
          // Красная точка записи была бы враньём - в системе красный это ошибка.
          // Зелёная рамка значит «в эфире», ровно как точка на пилюле во время
          // настоящей диктовки.
          rec ? "border-success" : "border-border",
        )}
      >
        {rec ? (
          <MicWave running={visible && rec} bars={32} barWidth={4} gap={4} maxHeight={56} />
        ) : result ? (
          <p
            className="w-full self-start font-sans text-md leading-[1.3] text-text transition-[opacity,transform] duration-[var(--dur-slow)] ease-out"
            style={{
              opacity: shown ? 1 : 0,
              // Подъём на 6 px - тот же, которым всплывает пилюля.
              transform: `translateY(${shown ? 0 : 6}px)`,
            }}
          >
            {result}
          </p>
        ) : (
          <p className="font-sans text-sm text-text-faint">
            {t("здесь появится ваш текст")}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------- 8. Править текст ----------
//
// Экран последний намеренно: сначала человек увидел, что диктовка работает, и
// только потом ему предлагают её улучшить. Предлагать улучшение до того, как
// заработало основное, - значит просить доверия авансом.

function LlmStep({ onFinish }: { onFinish: () => void }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [stage, setStage] = useState("");
  const [frac, setFrac] = useState(0);
  const [total, setTotal] = useState(0);
  const shown = useAppear(done);

  useEffect(() => {
    const offStage = on("llmStage", (s, f, tot) => {
      setStage(String(s ?? ""));
      setFrac(Number(f) || 0);
      setTotal(Number(tot) || 0);
    });
    const offDone = on("llmDone", (ok) => {
      setBusy(false);
      setDone(ok === true);
      setFailed(ok !== true);
    });
    return () => {
      offStage();
      offDone();
    };
  }, []);

  const pct = Math.round(Math.max(0, Math.min(1, frac)) * 100);

  return (
    <div className="flex flex-col gap-3">
      <StepTitle>{done ? t("Готово") : t("Осталось поставить правку текста")}</StepTitle>

      {/* Обещание переписано: раньше здесь стояло «без неё программа работать не
          будет», и это перестало быть правдой. Знаки препинания ставят правила,
          оговорки чинит corrections.py - обязательной работы у Ollama не
          осталось. Пугать человека тем, чего не случится, нельзя, тем более на
          последнем шаге, где кнопка «Дальше» ждёт установки. */}
      <StepNote className="leading-[1.4]">
        {done
          ? t("Всё готово. Программа умеет преобразовывать выделенный ") +
            t("текст и править его голосом.")
          : t("Диктовка работает и без неё: знаки препинания и оговорки ") +
            t("программа чинит сама. Правка текста нужна для другого - ") +
            t("преобразовать выделенное по одному нажатию: короче, строже, ") +
            t("списком, заданием для ИИ.")}
      </StepNote>

      {/* Цена названа ДО кнопки, а не после нажатия. 3.3 ГБ - это втрое больше
          самой программы вместе с моделью распознавания, и узнать об этом
          человек должен заранее. */}
      {!busy && !done ? (
        <div className="flex w-full flex-col gap-2 rounded-lg border border-border bg-paper px-4 py-3.5">
          <span className="font-sans text-sm font-semibold text-text">
            {t("Нужно скачать 3.3 ГБ")}
          </span>
          <span className="font-sans text-2xs leading-[1.4] text-text-muted">
            {t("Ollama - бесплатная программа, которая считает это на вашем ") +
              t("компьютере, и модель к ней. Всё останется здесь: интернет ") +
              t("нужен только чтобы скачать.")}
          </span>
        </div>
      ) : null}

      {/* Ход установки: этап словами и полоса. Проценты без этапа врут - «40%»
          ничего не значит, если непонятно, чего именно сорок. */}
      {busy ? (
        <div className="flex w-full flex-col gap-2">
          <span className="font-sans text-sm text-text">
            {total > 0
              ? `${stage} · ${pct}${t("% из ")}${(total / 1e9).toFixed(1)}${t(" ГБ")}`
              : stage}
          </span>
          <div
            role="progressbar"
            aria-label={t("Осталось поставить правку текста")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            className="h-1.5 w-full overflow-hidden rounded-full bg-fill"
          >
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-[var(--dur)] ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="font-sans text-2xs text-text-muted">
            {t("Можно свернуть окно - диктовка уже работает.")}
          </span>
        </div>
      ) : null}

      {/* Конец установки. Три гигабайта ждут долго, и молчаливое исчезновение
          полосы - плохая награда за ожидание: та же галка и тот же кивок, что на
          экране модели, отвечают на «ну как?». */}
      {done ? (
        <div
          className="flex items-center gap-2 transition-[opacity,transform] duration-[var(--dur-slow)] ease-out"
          style={{ opacity: shown ? 1 : 0, transform: `scale(${shown ? 1 : 0.96})` }}
        >
          <Icon name="check" size={16} strokeWidth={2.2} className="text-success" />
          <span className="font-sans text-sm text-success">
            {t("Правка текста на месте - можно закрывать мастер.")}
          </span>
        </div>
      ) : null}

      {!busy && !done ? (
        <div className="flex gap-3">
          <Button
            label={failed ? t("Попробовать снова") : t("Да, установить")}
            kind="primary"
            onClick={() => {
              setFailed(false);
              setBusy(true);
              setStage(t("начинаю"));
              setFrac(0);
              setTotal(0);
              void llmInstall();
            }}
          />
          {/* «Позже» возвращена по решению владельца: правка текста снова
              необязательна. Знаки препинания ставят правила, оговорки чинит
              corrections.py - без Ollama диктовка работает целиком, и запирать
              человека на этом шаге ради 3.3 ГБ нельзя. Путь тот же, что у нижней
              «Готово»: finish() закроет мастер без установки. */}
          <Button label={t("Позже")} onClick={onFinish} />
        </div>
      ) : null}

      {failed ? (
        <p className="w-full font-sans text-2xs leading-[1.4] text-danger">
          {t("Не получилось - ") +
            stage +
            t(". Диктовка работает и без этого, ") +
            t("а попробовать снова можно в настройках.")}
        </p>
      ) : null}

      {/* Последняя строка мастера - пожелание, а не указание, и стоит она ниже
          всех нарочно: человек дочитал до конца настройки, дальше только кнопка
          «Готово». Прощаться голым «Готово» невежливо.

          Прячем на время установки: там идёт полоса загрузки на 3.3 ГБ, и желать
          приятного посреди чужой работы рано. Во всех остальных состояниях -
          включая «Позже» и неудачу - строка на месте: диктовка работает в любом
          из них, и мастер для человека кончился. */}
      {!busy ? (
        <p className="w-full pt-2 font-sans text-sm text-text-secondary">
          {t("Приятного использования.")}
        </p>
      ) : null}
    </div>
  );
}
