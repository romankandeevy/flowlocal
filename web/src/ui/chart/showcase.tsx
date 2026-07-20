// Витрина рисованных контролов: метрики, графики, календарь, клавиши.
//
// Про эти семь нельзя написать проверку «нарисовано правильно»: столбик либо
// есть, либо нет, а вот перепутанные рекорд и «сегодня», слипшийся на восьми
// пикселях календарь или число, которое досчитывает уже после того, как
// страница встала, видны только глазом. Поэтому данные здесь выдуманные, но
// правдоподобные: пустой день среди недели, рекорд не в последнем столбце,
// серия меньше рекорда, ожидающая метрика без числа.
//
// Числа постоянные, а не случайные при каждой сборке: витрину открывают, чтобы
// сравнить с прошлым разом, и плавающие данные это сравнение убивают.

import { useEffect, useState, type ReactNode } from "react";

import { Button } from "../button";
import { Card } from "../card";
import { Heading, Note } from "../text";
import { BarChart, type WeekDay } from "./bar-chart";
import { KeyCaps } from "./key-caps";
import { Metric } from "./metric";
import { SpeedBars } from "./speed-bars";
import { StreakCalendar, type CalendarDay, type CalendarMonth } from "./streak-calendar";
import { StreakRing } from "./streak-ring";
import { decayPeak, levelFromRms, WaveMeter } from "./wave-meter";

// Семь последних дней, заканчивая сегодняшним, - так их и отдаёт stats.week,
// поэтому «сегодня» здесь всегда последний столбец, а подписи начинаются не с
// понедельника. Данные согласованы с календарём ниже: та же неделя тех же
// чисел июля.
const WEEK: WeekDay[] = [
  { label: "вс", value: 190, today: false, hint: "19 июля · 190 слов" },
  { label: "пн", value: 120, today: false, hint: "20 июля · 120 слов" },
  { label: "вт", value: 340, today: false, hint: "21 июля · 340 слов" },
  // Пустой день посреди недели - проверка, что ниточка на месте и что по ней
  // можно навести мышь.
  { label: "ср", value: 0, today: false, hint: "22 июля · 0 слов" },
  { label: "чт", value: 210, today: false, hint: "23 июля · 210 слов" },
  // Рекорд недели не в последнем столбце: иначе не видно, что подсветка
  // рекорда и подсветка «сегодня» - разные вещи.
  { label: "пт", value: 480, today: false, hint: "24 июля · 480 слов" },
  { label: "сб", value: 60, today: true, hint: "25 июля · 60 слов" },
];

const WEEK_AVG = 200;

const WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

const CAL_WEEKS = 26;

// Столбцы месяцев посчитаны от той же даты, что и подсказки: если разъедутся,
// «июл» встанет над июньскими клетками и витрина будет врать ровно тем, ради
// чего её и смотрят.
const CAL_MONTHS: CalendarMonth[] = [
  { label: "фев", col: 0 },
  { label: "мар", col: 4 },
  { label: "апр", col: 9 },
  { label: "май", col: 13 },
  { label: "июн", col: 18 },
  { label: "июл", col: 22 },
];

const MONTH_NAMES = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

// Последняя клетка сетки - воскресенье текущей недели, как его считает
// stats.calendar. Дата постоянная, а не new Date(): витрина должна выглядеть
// одинаково и сегодня, и через год, иначе её не с чем сравнивать.
const CAL_LAST = new Date(2026, 6, 26);

/**
 * Полгода клеток. Порядок - столбец за столбцом сверху вниз, как его отдаёт
 * stats.calendar: внутри недели соседние даты - соседние дни недели.
 *
 * Раскладка нарочно неровная и нарочно согласована с дугой рядом: рекорд -
 * девять дней подряд в прошлом, текущая серия - пять, перед ней обрыв, в
 * середине окна две недели молчания. Дуга показывает пять из девяти, и на
 * клетках это должно сходиться - иначе витрина проверяет сама себя не тем.
 */
function fakeCalendar(): CalendarDay[] {
  const out: CalendarDay[] = [];
  const total = CAL_WEEKS * 7;
  // Сегодня - суббота последней недели, дальше только будущее.
  const todayIndex = total - 2;

  for (let i = 0; i < total; i++) {
    const week = Math.floor(i / 7);
    const dow = i % 7;
    // Ровный, но неповторяющийся узор без генератора случайных: два простых
    // множителя дают достаточно рваную картинку и одинаковы при каждой сборке.
    const noise = (i * 7 + week * 3) % 5;
    let level = dow >= 5 ? noise % 2 : Math.min(4, 1 + (noise % 4));
    // Отпуск: две недели молчания.
    if (week >= 11 && week <= 12) level = 0;
    // Рекорд - девять дней подряд, с обрывом по обе стороны.
    if (i >= 100 && i < 109) level = Math.max(2, level);
    if (i === 99 || i === 109) level = 0;
    // Текущая серия - пять дней, обрыв прямо перед ней.
    if (i > todayIndex - 5 && i <= todayIndex) level = Math.max(1, level);
    if (i === todayIndex - 5) level = 0;

    // Слова кратны десяти нарочно: склонение числительных в настоящих
    // подсказках делает Python, а витрина не должна изобретать своё и писать
    // «1 слов». На десятках форма одна на все числа.
    const words = level === 0 ? 0 : level * 90 + (i % 5) * 10;
    const day = new Date(CAL_LAST);
    day.setDate(day.getDate() - (total - 1 - i));
    const future = i > todayIndex;

    out.push({
      level,
      today: i === todayIndex,
      future,
      // У будущих дней подсказки нет: «0 слов» про послезавтра утверждало бы,
      // что там уже ноль.
      hint: future
        ? ""
        : `${day.getDate()} ${MONTH_NAMES[day.getMonth()] ?? ""} · ${words} слов`,
    });
  }
  return out;
}

const CALENDAR = fakeCalendar();

export function ChartShowcase() {
  const [calOpen, setCalOpen] = useState(false);

  return (
    <>
      <Section title="Метрики">
        {/* Три в ряд одной строкой сетки: карточки тянутся по самой высокой, и
            ряд остаётся ровным, даже когда у одной значение переносится. */}
        <div className="grid grid-cols-3 items-stretch gap-3">
          <Metric
            order={0}
            icon="timer"
            label="сэкономлено"
            value="46 с"
            hint="по сравнению с печатью руками"
          />
          <Metric
            order={1}
            label="скорость"
            pending
            value="Наговорите минуту - посчитаем"
          />
          <Metric
            order={2}
            icon="type"
            label="надиктовано"
            countTo={12480}
            hint="слов за всё время"
          />
        </div>
        <Note>
          Слева готовая строка из Python, посередине - ожидание вместо числа,
          справа счётчик добегает от нуля. Тени нет ни у одной: внутри движется
          содержимое.
        </Note>
      </Section>

      <Section title="Серия">
        <div className="grid grid-cols-3 items-stretch gap-3">
          <Metric order={0} icon="stats" label="слов всего" countTo={12480} />
          <Metric order={1} icon="timer" label="сэкономлено" value="3 ч 20 мин" />
          <StreakRing
            value={5}
            best={9}
            label="дней подряд"
            record="рекорд 9"
            expandable
            open={calOpen}
            onActivate={() => setCalOpen((v) => !v)}
          />
        </div>
        {calOpen ? (
          // Внутри ничего не движется, кроме подсказки под курсором, - тень
          // пересчитывалась бы на каждое наведение мыши.
          <Card shadow={false}>
            <div className="px-6 py-4">
              <StreakCalendar
                days={CALENDAR}
                months={CAL_MONTHS}
                weekdays={WEEKDAYS}
                weeks={CAL_WEEKS}
              />
            </div>
          </Card>
        ) : null}
        <Note>
          Дуга - доля текущей серии от рекорда, а не от круглого числа. Нажатие
          раскрывает календарь: он живёт своей карточкой под рядом, потому что
          третья метрика не может развернуться на всю ширину, не сломав сетку.
        </Note>
      </Section>

      <Section title="По дням">
        <Card shadow={false}>
          <div className="px-6 py-4">
            <BarChart days={WEEK} avg={WEEK_AVG} />
          </div>
        </Card>
        <Note>
          Сегодня акцентом, рекорд недели плотными чернилами, пустой день -
          ниточкой. Пунктир - средний день недели, число считает Python.
        </Note>
      </Section>

      <Section title="Скорость">
        <SpeedBars typingWpm={40} voiceWpm={122} ratio="в 3,0 раза" />
      </Section>

      <Section title="Волна микрофона">
        <MicDemo />
      </Section>

      <Section title="Клавиши">
        <Card>
          <div className="flex flex-col gap-4 px-6 py-4">
            <KeyCaps combo="Ctrl + Shift + Space" />
            <KeyCaps combo="Ctrl + Shift + Space" down={[true, true, false]} />
            <KeyCaps combo="Ctrl + Shift + Space" lit />
            {/* Длинное сочетание - проверка переноса: «+» обязан уехать на
                новую строку вместе со своей клавишей. */}
            <KeyCaps combo="Ctrl + Alt + Shift + Space" />
          </div>
        </Card>
        <Note>
          Обычные, две зажаты, сочетание собрано целиком. Зелёный - «работает, в
          эфире», а не «выделено».
        </Note>
      </Section>
    </>
  );
}

/**
 * Волна на выдуманном микрофоне.
 *
 * Замеры сюда подаёт витрина, а не компонент: он и в программе за данными не
 * ходит. Молчит, пока не нажали, - и потому что так честнее показывает покой, и
 * потому что тикающий таймер в витрине, открытой на весь день, ни к чему.
 */
function MicDemo() {
  const [running, setRunning] = useState(false);
  const [levels, setLevels] = useState<number[]>([]);
  const [peak, setPeak] = useState(0);

  useEffect(() => {
    if (!running) {
      setLevels([]);
      setPeak(0);
      return;
    }
    let phase = 0;
    const id = setInterval(() => {
      // Речь идёт волнами: громко на слове, тихо между словами. Ровный шум дал
      // бы забор, по которому не видно, слышно человека или нет.
      phase += 0.16;
      const wave = Math.max(0, Math.sin(phase)) ** 2;
      const level = levelFromRms(wave * 0.26 + 0.004);
      setLevels((prev) => [...prev, level].slice(-40));
      setPeak((prev) => decayPeak(prev, level));
    }, 33);
    return () => clearInterval(id);
  }, [running]);

  return (
    <Card shadow={false}>
      <div className="flex flex-col items-center gap-4 px-6 py-6">
        <WaveMeter levels={levels} />
        <div className="flex items-center gap-2">
          {/* Слово к волне. Форму человек видит, но вывод из неё делает не
              сразу: «ровно» и «чуть шевелится» на глаз похожи, а решение на
              этом экране принимается одно - тот микрофон или не тот. */}
          <span
            className="block h-2 w-2 shrink-0 rounded-full transition-colors duration-[var(--dur-fast)]"
            style={{
              background:
                peak > 0.45 ? "var(--color-success)" : "var(--color-text-faint)",
            }}
          />
          <span className="font-sans text-sm text-text-secondary">
            {peak > 0.45 ? "слышу вас" : "тихо"}
          </span>
        </div>
        <Button
          label={running ? "Остановить" : "Проверить микрофон"}
          onClick={() => setRunning((v) => !v)}
        />
      </div>
    </Card>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <Heading>{title}</Heading>
      {children}
    </section>
  );
}
