// Каркас мастера первого запуска: шаги, полоска прогресса, «Назад» и «Дальше».
//
// Содержимое экранов - в steps.tsx, живая волна - в mic-wave.tsx. Здесь то, что
// обязано быть в одном месте: номер шага, состояние модели и слежка за
// настоящим нажатием сочетания.
//
// **Почему слежка живёт здесь, а не на экранах жестов.** В QML она сперва
// стояла в самих экранах, и с одним экраном жестов работала. С двумя ломается:
// при «Назад» сигналы видимости двух экранов приходят в порядке объявления, а
// не в порядке «сначала сними старое, потом взведи новое». Экран, на который
// возвращаешься, успевал взвести слежку, а уходящий тут же снимал её вместе с
// хоткеями приложения - программа оставалась немой. Хозяин обязан быть один, и
// хук ровно один за раз; ровно это делает syncWatch.
//
// Мастер водят с клавиатуры: Enter ведёт вперёд. Это девять нажатий подряд, и
// рука уже лежит на клавиатуре - в мастере, который учит нажимать клавиши,
// тянуться за мышью ради «Дальше» странно.
import { useCallback, useEffect, useRef, useState } from "react";

import {
  downloadStarter,
  englishReady,
  finish,
  getSetting,
  modelsInfo,
  on,
  pretty,
  recommended,
  setModel,
  setSetting,
  unwatchHotkey,
  watchHotkey,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { cn } from "../ui/cn";
import { Steps, type Combo, type ModelState } from "./steps";

/** Номер последнего шага. Экранов девять: 0 - привет, 8 - правка текста. */
const LAST = 8;

/**
 * Умолчание для второго жеста. В конфиге он пуст по замыслу - жест
 * необязательный, но экран обязан что-то показать и проверить живьём.
 *
 * Почему ctrl+shift+d, а не боковая кнопка мыши: экран заставляет жест
 * ВЫПОЛНИТЬ, пока не выполнил - «Дальше» заперта. Значит умолчание должно
 * нажиматься на ЛЮБОЙ машине. Боковой кнопки у отца и друзей - тех, для кого
 * программа, - может не быть вовсе (ноутбук, трекпад), и человек застрял бы на
 * пустом жесте. Клавиши есть у всех. С удержанием (ctrl+shift+space) не
 * конфликтует, буква d - от «диктовки».
 */
const TOGGLE_DEFAULT = "ctrl+shift+d";

/** Строка каталога моделей - то, что отдаёт Backend.modelsInfo. */
interface ModelRow {
  id?: string;
  installed?: boolean;
  downloading?: boolean;
}

const EMPTY_COMBO: Combo = {
  spec: "",
  pretty: "",
  down: [],
  lit: false,
  verified: false,
};

export function Wizard() {
  const [step, setStep] = useState(0);

  const [chosen, setChosen] = useState("");
  const [ready, setReady] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [frac, setFrac] = useState(0);

  const [hold, setHold] = useState<Combo>(EMPTY_COMBO);
  const [toggle, setToggle] = useState<Combo & { skipped: boolean }>({
    ...EMPTY_COMBO,
    skipped: false,
  });
  // Отказ от второго жеста нужен и слежке, а она читает его из замыкания,
  // сложившегося до отказа. В QML присвоение свойства видно сразу же, здесь
  // роль «сразу же» играет ref, а состояние рядом - для отрисовки.
  const skippedRef = useRef(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  // ---------- модель ----------

  useEffect(() => {
    // По умолчанию - рекомендация для русского. Считает её Python: каталог
    // моделей его, и второе мнение о «какую взять» тут лишнее.
    void recommended().then((v) => setChosen(String(v ?? "")));
  }, []);

  // «Готово» - это когда на месте ОБЕ модели: русская и английская. Вторая не
  // выбирается и не ищется в настройках, она приезжает вместе с первой - иначе
  // человек увидел бы, что английский не даётся, и пошёл бы искать настройку,
  // которой нет (решение владельца).
  const refreshModel = useCallback(async () => {
    if (!chosen) return;
    const [list, eng] = await Promise.all([modelsInfo(), englishReady()]);
    const row = (list as ModelRow[]).find((m) => m?.id === chosen);
    if (!row) {
      setReady(false);
      return;
    }
    setReady(row.installed === true && eng === true);
    setDownloading(row.downloading === true);
  }, [chosen]);

  useEffect(() => {
    void refreshModel();
  }, [refreshModel]);

  useEffect(
    () =>
      on("modelsChanged", () => {
        void refreshModel();
      }),
    [refreshModel],
  );

  useEffect(
    () =>
      on("modelProgress", (id, f) => {
        if (String(id) === chosen) setFrac(Number(f) || 0);
      }),
    [chosen],
  );

  // ---------- живое нажатие сочетаний ----------

  const syncWatch = useCallback(async () => {
    if (step === 4) {
      const spec = String((await getSetting("hotkey_hold")) ?? "");
      const nice = spec ? String(await pretty(spec)) : "";
      setHold((c) => ({ ...c, spec, pretty: nice, down: [], lit: false }));
      void watchHotkey(spec);
      return;
    }
    if (step === 5) {
      // Умолчание предлагаем ЛОКАЛЬНО, в конфиг не пишем: пока человек не
      // доказал жест и не нажал «Дальше», навязывать ему сочетание нечестно. В
      // конфиг оно ляжет на «Дальше» - или пустота, на «Мне хватит одного».
      let cur = String((await getSetting("hotkey_toggle")) ?? "");
      if (cur === "" && !skippedRef.current) cur = TOGGLE_DEFAULT;
      const nice = cur ? String(await pretty(cur)) : "";
      setToggle((c) => ({ ...c, spec: cur, pretty: nice, down: [], lit: false }));
      void watchHotkey(cur);
      return;
    }
    void unwatchHotkey();
  }, [step]);

  useEffect(() => {
    void syncWatch();
  }, [syncWatch]);

  // Уйти из мастера с немой программой нельзя: слежка снимает хоткеи
  // приложения на себя, и вернуть их обязан тот, кто забирал. finish() делает
  // это на стороне Python, но окно закрывают и мимо кнопки.
  useEffect(
    () => () => {
      void unwatchHotkey();
    },
    [],
  );

  useEffect(
    () =>
      on("comboState", (down, lit) => {
        const flags = Array.isArray(down) ? down.map((v) => v === true) : [];
        const full = lit === true;
        // Латч verified не гаснет, когда человек отпустил клавиши, и переживает
        // уход на соседний экран и обратно. Ровно он отпирает «Дальше».
        if (step === 4)
          setHold((c) => ({ ...c, down: flags, lit: full, verified: c.verified || full }));
        else if (step === 5)
          setToggle((c) => ({ ...c, down: flags, lit: full, verified: c.verified || full }));
      }),
    [step],
  );

  useEffect(
    () =>
      on("captureDone", (which) => {
        const field = String(which);
        // Сочетание сменили - доказательство обнуляем и перевзводим слежку под
        // новый spec. Заодно она заберёт назад снятые захватом хоткеи
        // приложения, иначе нажатие ушло бы в настоящую диктовку.
        if (field === "hotkey_hold" && step === 4) {
          setHold((c) => ({ ...c, verified: false }));
          void syncWatch();
        }
        // Назначил своё - значит жест ему нужен: отказ снимаем.
        if (field === "hotkey_toggle" && step === 5) {
          skippedRef.current = false;
          setToggle((c) => ({ ...c, skipped: false, verified: false }));
          void syncWatch();
        }
      }),
    [step, syncWatch],
  );

  // ---------- ход по шагам ----------

  // Новый шаг - с начала: прокрутка одного не должна доставаться другому.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [step]);

  // Живая проверка жестов запирает «Дальше»: на экране удержания - пока
  // сочетание не зажали хоть раз, на экране второго жеста - пока не доказали
  // ЛИБО не отказались явно. Остальные шаги не трогаем: у модели блокировка
  // своя, через сам обработчик (скачать, а не пройти дальше).
  //
  // Последний шаг больше не запирает: владелец сделал правку текста
  // необязательной. Раньше кнопка ждала установки Ollama - без неё модель
  // отдавала текст без знаков препинания; теперь их ставят правила, и «Готово»
  // выпускает человека с рабочей диктовкой.
  const nextEnabled =
    step === 4 ? hold.verified : step === 5 ? toggle.verified || toggle.skipped : true;

  const goNext = useCallback(() => {
    if (step === 2 && !ready) {
      // downloadStarter, а не downloadModel: качаются обе модели подряд,
      // русская и английская, одной полосой.
      if (!downloading) void downloadStarter(chosen);
      return;
    }
    if (step === 2 && ready) void setModel(chosen);
    // Второй жест доказан - только теперь пишем его в конфиг. До «Дальше»
    // умолчание жило локально, см. syncWatch.
    if (step === 5) setSetting("hotkey_toggle", toggle.spec);
    if (step === LAST) {
      void finish(); // finish() сам закроет окно
      return;
    }
    setStep((s) => s + 1);
  }, [step, ready, downloading, chosen, toggle.spec]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || e.defaultPrevented) return;
      // Кнопку, поле и переключатель Enter нажимает сам, и перехватывать его у
      // них нельзя: в QML ради этого мастер отбирал фокус обратно на каждом
      // шаге, здесь достаточно не мешать тому, на ком фокус стоит.
      const el = e.target;
      if (
        el instanceof Element &&
        el.closest(
          "button, input, textarea, select, summary, [role='switch'], [role='combobox']",
        )
      )
        return;
      if (!nextEnabled) return;
      goNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, nextEnabled]);

  const model: ModelState = { chosen, ready, downloading, frac };

  const nextLabel =
    step === 0
      ? t("Начать")
      : step === 2
        ? ready
          ? t("Дальше")
          : downloading
            ? t("Скачивается…")
            : t("Скачать")
        : step === LAST
          ? t("Готово")
          : t("Дальше");

  // Точки говорят «сколько всего» и «где-то тут», но не отвечают на вопрос «на
  // каком я»: девять точек по десять пикселей глазом не пересчитываются - это
  // работа, а не подсказка. К концу пути подпись меняется на «почти готово» и
  // «последний шаг»: там важнее не номер, а то, что осталось немного. Разбор
  // онбординга Wispr Flow отмечает ровно это - человек охотнее идёт дальше,
  // когда знает, что осталось чуть-чуть, чем когда видит полную длину пути.
  const caption =
    step === LAST
      ? t("последний шаг")
      : step === LAST - 1
        ? t("почти готово")
        : t("шаг ") + (step + 1) + t(" из ") + (LAST + 1);

  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <header className="flex shrink-0 flex-col items-center gap-2 pt-6">
        {/* Полоска прогресса - настоящая, с ролью и числом. В QML это ряд
            прямоугольников, и для диктора он немой: ни что идёт мастер, ни
            сколько осталось, он не сообщает вовсе. */}
        <div
          role="progressbar"
          aria-label={t("Ход настройки")}
          aria-valuemin={1}
          aria-valuemax={LAST + 1}
          aria-valuenow={step + 1}
          aria-valuetext={caption}
          className="flex items-center gap-2"
        >
          {Array.from({ length: LAST + 1 }, (_unused, i) => (
            // Текущий шаг - не точка, а короткая полоска: форма читается
            // боковым зрением, а оттенок в ряду одинаковых кружков - нет. Она
            // же и есть отклик на «Дальше»: полоска переезжает, точки
            // перекрашиваются. Состояний три, а не два: пройденное, текущее,
            // будущее - раньше первые два красились одинаково, и ряд отвечал
            // только на «сколько всего».
            <span
              key={i}
              aria-hidden="true"
              className={cn(
                "h-[10px] rounded-full",
                "transition-[width,background-color] duration-[var(--dur)] ease-out",
                i === step
                  ? "w-6 bg-ink"
                  : i < step
                    ? "w-[10px] bg-ink/35"
                    : "w-[10px] bg-fill-strong",
              )}
            />
          ))}
        </div>
        <span className="font-sans text-2xs text-text-muted">{caption}</span>
      </header>

      {/* Прокрутка нужна не «на всякий случай». Окно у мастера маленькое, а шаги
          разной высоты: у одного заголовок и кнопка, у другого выбор темы,
          образец настроек и объяснение. Пока содержимое лезло за край, оно
          наезжало на «Назад» и «Дальше» - кнопки оказывались ПОД текстом, и это
          ровно то, что владелец описал как «нажал переключатель, всё пропало». */}
      <main ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-8 py-8">
        <Steps
          wiz={{
            step,
            model,
            hold,
            toggle,
            onSkipToggle: () => {
              skippedRef.current = true;
              setToggle((c) => ({ ...c, skipped: true, verified: false }));
              setSetting("hotkey_toggle", ""); // отказ - значит пусто в конфиге
              setStep((s) => s + 1);
            },
            onFinish: () => {
              void finish();
            },
          }}
        />
      </main>

      <footer className="flex h-[72px] shrink-0 items-center justify-between px-8">
        {step > 0 ? (
          <Button label={t("Назад")} onClick={() => setStep((s) => s - 1)} />
        ) : (
          // Пустышка держит «Дальше» у правого края на первом экране: без неё
          // единственная кнопка уехала бы влево, и первый шаг выглядел бы иначе
          // всех остальных.
          <span />
        )}
        <Button
          label={nextLabel}
          kind="primary"
          disabled={!nextEnabled}
          onClick={goNext}
        />
      </footer>
    </div>
  );
}
