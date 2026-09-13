// Страница «Статистика»: три числа крупно, неделя столбиками, разбор речи.
//
// Ключей конфига у страницы нет ни одного, поэтому сверка config.json на ней не
// ловит НИЧЕГО: её можно перенести пустой, и дампы совпадут. Всё держится на
// втором критерии фазы 4 - четыре вызова Backend (stats, calendar, insights,
// addToDictionary) должны делать то же, что в QML-версии. Каждый ниже помечен.
//
// Календарь серии тянется не вместе со страницей, а в момент, когда на дугу
// нажали. Довод из QML переносится как есть: B.calendar() читает историю с
// диска и собирает полтораста клеток с подписями, и платить за них тому, кто
// на дугу не нажимал, незачем.
//
// В QML страница жила в дереве всегда и перечитывала числа по onVisibleChanged.
// Здесь роутер держит только текущую страницу, остальные размонтированы, то
// есть «заход на страницу» - это монтирование, и чтение идёт из useEffect.
// Оговорка QML «раскрытый календарь обновляем вместе со всем остальным» отсюда
// уходит сама: развёрнутым он пережить уход со страницы уже не может.
import { useEffect, useState } from "react";

import {
  addToDictionary,
  calendar,
  getSetting,
  insights,
  pretty,
  stats,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { BarChart, type WeekDay } from "../ui/chart/bar-chart";
import { KeyCaps } from "../ui/chart/key-caps";
import { Metric } from "../ui/chart/metric";
import { SpeedBars } from "../ui/chart/speed-bars";
import {
  StreakCalendar,
  type CalendarDay,
  type CalendarMonth,
} from "../ui/chart/streak-calendar";
import { StreakRing } from "../ui/chart/streak-ring";
import { StatRow } from "../ui/form/stat-row";
import { EmptyState } from "../ui/misc/empty-state";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";

/** Сводка от B.stats(). Строки собраны в Python - там же, где склонение. */
interface Stats {
  hasData?: boolean;
  dictations?: string;
  words?: string;
  seconds?: string;
  saved_sec?: string;
  speedOk?: boolean;
  speed?: string;
  userWpm?: number;
  streakDays?: number;
  streakBest?: number;
  weekAvg?: number;
  week?: WeekDay[];
  hasBest?: boolean;
  bestWords?: string;
  bestDate?: string;
  typingWpm?: number;
}

interface Calendar {
  weeks?: number;
  weekdays?: string[];
  months?: CalendarMonth[];
  days?: CalendarDay[];
}

/** Слово, которое программа поправила: как услышалось, как надо, сколько раз. */
interface Confusion {
  heard: string;
  fixed: string;
  n: number;
}

/** Куда диктуете: вид программы, доля, слова, число диктовок. */
interface Place {
  kind: string;
  share: number;
  words: number;
  count: number;
}

interface Insights {
  rows?: number;
  words?: number;
  enough?: boolean;
  persona?: string;
  top_word?: string;
  top_word_n?: number;
  phrase?: string;
  hourText?: string;
  fixed?: number;
  pairs?: Confusion[];
  where?: Place[];
}

export function StatsPage() {
  const [s, setS] = useState<Stats>({});
  const [ins, setIns] = useState<Insights>({ rows: 0 });
  const [calOpen, setCalOpen] = useState(false);
  const [cal, setCal] = useState<Calendar>({});
  // Сочетание нужно пустому состоянию: человеку тут нечего делать, кроме как
  // пойти и продиктовать, и показать ему надо форму клавиши, а не слово
  // «Ctrl» посреди абзаца.
  const [combo, setCombo] = useState("");

  useEffect(() => {
    // ВЫЗОВ B.stats() - числа страницы.
    void stats().then((v) => setS(v as Stats));
    // ВЫЗОВ B.insights() - разбор речи. В QML он звался и при сборке окна, и
    // при каждом заходе; здесь заход и есть сборка, поэтому один раз.
    void insights().then((v) => setIns(v as Insights));
    void reloadHotkey();
  }, []);

  // Сырые значения, а не pretty(): у пустого сочетания pretty() возвращает
  // «не задано» - непустую строку, и проверка на ней всегда истинна. Ровно на
  // этом карточка когда-то писала «Зажмите не задано и говорите».
  async function reloadHotkey() {
    const hold = String((await getSetting("hotkey_hold")) ?? "");
    const toggle = String((await getSetting("hotkey_toggle")) ?? "");
    const raw = hold || toggle;
    setCombo(raw ? await pretty(raw) : "");
  }

  async function toggleCalendar() {
    const next = !calOpen;
    setCalOpen(next);
    // ВЫЗОВ B.calendar() - клетки по дням. Один раз за жизнь страницы: данные
    // за полгода внутри одного захода не меняются.
    if (next && cal.days === undefined) setCal((await calendar()) as Calendar);
  }

  const week = s.week ?? [];
  const confusions = (ins.pairs ?? []).slice(0, 3);
  const places = ins.where ?? [];

  return (
    <>
      <Heading level="page">{t("Статистика")}</Heading>

      {/* Пусто - зовём попробовать, а не показываем пять нулей: шеренга нулей
          читается как «программа сломана», а не как «вы ещё не начали». */}
      {s.hasData === false ? (
        <Card>
          <EmptyState
            icon="stats"
            title={t("Здесь появятся ваши числа")}
            combo={combo ? <KeyCaps combo={combo} /> : undefined}
            hint={
              combo === ""
                ? t("Сначала задайте сочетание на странице «Диктовка».")
                : t("Скажите что-нибудь. Счёт слов, времени и дней ") +
                  t("подряд пойдёт с первой же диктовки.")
            }
            alarm={combo === ""}
          />
        </Card>
      ) : null}

      {s.hasData === true ? (
        <>
          {/* Три числа крупно и первыми, до всяких списков. Сетка из трёх, а не
              перенос по ширине: Metric сам разбирается с длинным значением, а
              ряд обязан оставаться рядом при любой ширине окна. */}
          <div className="grid grid-cols-3 gap-3">
            <Metric
              order={0}
              icon="type"
              label={t("слов всего")}
              // Чистый счётчик - его и оживляем: бежит от нуля.
              countTo={Number.parseInt(String(s.words ?? "0"), 10) || 0}
            />
            <Metric
              order={1}
              icon="timer"
              label={t("сэкономлено")}
              value={String(s.saved_sec ?? "")}
            />
            {/* Серия - дугой, а не голым числом: наглядная доля от рекорда.
                Нажатие раскрывает календарь по дням - карточкой ниже, потому
                что метрика в ряду из трёх не может развернуться во всю ширину,
                не сломав сетку. */}
            <StreakRing
              value={s.streakDays ?? 0}
              best={s.streakBest ?? 0}
              label={t("дней подряд")}
              record={
                (s.streakBest ?? 0) > 0 ? `${t("рекорд")} ${s.streakBest}` : ""
              }
              expandable
              open={calOpen}
              onActivate={() => void toggleCalendar()}
            />
          </div>

          {calOpen ? (
            // Тень выключена: внутри двигается подсказка под курсором, и тень
            // поднимала бы слой на композитор на каждое наведение мыши.
            <Card shadow={false}>
              <div className="px-6 py-4">
                <StreakCalendar
                  days={cal.days ?? []}
                  months={cal.months ?? []}
                  weekdays={cal.weekdays ?? []}
                  weeks={cal.weeks ?? 26}
                />
              </div>
            </Card>
          ) : null}

          <div className="flex flex-col gap-3">
            <Heading level="section">{t("По дням")}</Heading>
            <Card shadow={false}>
              <div className="px-6 py-4">
                <BarChart days={week} avg={s.weekAvg ?? 0} height={146} />
              </div>
              {/* Рекорд - в той же карточке, а не отдельной: он про те же
                  столбики, только за всю историю, и разделительной линии между
                  ними достаточно. */}
              {s.hasBest === true ? (
                <StatRow
                  title={t("Лучший день")}
                  subtitle={String(s.bestDate ?? "")}
                  value={String(s.bestWords ?? "-")}
                />
              ) : null}
            </Card>
          </div>

          {/* «Быстрее печати» видно только когда число честное (набралась
              минута речи): до этого множитель случаен, и рисовать полосу с
              потолка нельзя. */}
          {s.speedOk === true ? (
            <div className="flex flex-col gap-3">
              <Heading level="section">{t("Быстрее печати")}</Heading>
              <SpeedBars
                typingWpm={s.typingWpm ?? 40}
                voiceWpm={s.userWpm ?? 0}
                ratio={String(s.speed ?? "")}
              />
            </div>
          ) : null}

          <div className="flex flex-col gap-3">
            <Heading level="section">{t("Итого")}</Heading>
            <Card>
              {/* «Слов надиктовано» и «Дней подряд» отсюда ушли: они наверху
                  метриками, а строка, повторяющая метрику экраном ниже, не
                  добавляет ничего, кроме высоты.

                  «Сэкономлено» осталось, и это не недосмотр. Метрика
                  показывает число, а строка отвечает, откуда оно взялось:
                  сорок слов в минуту - оценка скорости набора, а не замер
                  конкретного человека. Убрать оговорку значит выдать прикидку
                  за факт, а число экономии - самое лестное на странице. */}
              <StatRow
                first
                title={t("Диктовок")}
                subtitle={t("Сколько раз вы говорили вместо того, чтобы печатать")}
                value={String(s.dictations ?? "-")}
              />
              <StatRow
                title={t("Наговорено")}
                subtitle={t("Столько вы говорили")}
                value={String(s.seconds ?? "-")}
              />
              <StatRow
                title={t("Сэкономлено")}
                subtitle={
                  t("Печатать это руками - примерно ") +
                  (s.typingWpm ?? 40) +
                  t(" слов в минуту. Столько вы сберегли")
                }
                value={String(s.saved_sec ?? "-")}
              />
            </Card>
          </div>
        </>
      ) : null}

      {/* ---- Как вы говорите ----
          Считается по накопленной истории, здесь же, на этой машине. Пока
          данных мало - раздела нет вовсе: сказать «ваше любимое слово -
          «который»» по трём диктовкам значит соврать с умным видом. */}
      {(ins.rows ?? 0) > 0 ? (
        <div className="flex flex-col gap-3">
          <Heading level="section">{t("Как вы говорите")}</Heading>
          <Card>
            {ins.persona ? (
              <StatRow first title={t("Ваша манера")} subtitle={ins.persona} value="" />
            ) : null}
            {ins.top_word ? (
              <StatRow
                title={t("Любимое слово")}
                subtitle={t("Чаще всего повторяется в ваших диктовках")}
                value={`${ins.top_word} · ${ins.top_word_n ?? 0}`}
              />
            ) : null}
            {ins.phrase ? (
              <StatRow
                title={t("Присказка")}
                subtitle={t("Три слова подряд, которые вы говорите чаще прочих")}
                value={ins.phrase}
              />
            ) : null}
            {ins.hourText ? (
              <StatRow
                title={t("Часы пик")}
                subtitle={t("Когда вы диктуете больше всего")}
                value={ins.hourText}
              />
            ) : null}
            {/* Было «Программа исправила: 10», и владелец справедливо спросил,
                что ему с этим числом делать. Теперь строка отвечает на «что
                делать»: есть слова, которые путаются, - вот они, с кнопкой;
                нет - число значит «всё в порядке, чинить нечего». */}
            {(ins.fixed ?? 0) > 0 ? (
              <StatRow
                title={t("Программа исправила")}
                subtitle={
                  confusions.length > 0
                    ? t("Столько слов она поправила за вас. Что путается чаще - ниже")
                    : t("Столько слов она поправила за вас. Ничего чинить не нужно")
                }
                value={String(ins.fixed ?? 0)}
              />
            ) : null}
            {/* Список, а не набор строк подряд: диктор объявляет «список, 3
                элемента» и умеет по нему прыгать. В QML это Repeater, и для
                диктора он немой. */}
            {confusions.length > 0 ? (
              <ul>
                {confusions.map((p) => (
                  <li key={p.heard}>
                    <SettingRow
                      title={`${t("Путается «")}${p.heard}»`}
                      subtitle={
                        t("Вы диктуете «") +
                        p.fixed +
                        t("», а слышится ") +
                        t("иначе. Уже ") +
                        p.n +
                        t(" раз")
                      }
                    >
                      {/* Научить программу за одно нажатие: открывать «Слова»
                          и вспоминать написание не нужно - мы его уже знаем. */}
                      <Button
                        label={t("Научить")}
                        // ВЫЗОВ B.addToDictionary(услышано, как надо).
                        onClick={() => void addToDictionary(p.heard, p.fixed)}
                      />
                    </SettingRow>
                  </li>
                ))}
              </ul>
            ) : null}
            {/* Пока не набралось - говорим сколько ещё, а не молчим. */}
            {!ins.enough ? (
              <StatRow
                title={t("Пока считаем")}
                subtitle={
                  t("Про любимое слово и присказку скажем, когда ") +
                  t("наберётся побольше диктовок")
                }
                value={`${ins.words ?? 0}${t(" слов")}`}
              />
            ) : null}
          </Card>
        </div>
      ) : null}

      {places.length > 0 ? (
        <div className="flex flex-col gap-3">
          <Heading level="section">{t("Куда диктуете")}</Heading>
          <Card>
            <ul>
              {places.map((p, i) => (
                <li key={p.kind}>
                  <StatRow
                    first={i === 0}
                    title={p.kind}
                    subtitle={`${p.words}${t(" слов за ")}${p.count}${t(" диктовок")}`}
                    value={`${p.share}%`}
                  />
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </>
  );
}
