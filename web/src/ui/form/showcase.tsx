// Витрина контролов форм: переключатель, сегменты, список, ползунок, поле,
// строка со статистикой.
//
// Смотреть надо ровно на то, что тестом не проверяется: сходятся ли радиусы у
// вложенных углов, не дёргается ли подпись ползунка при перетаскивании, видно
// ли, куда попадёт щелчок на трёх сегментах. Числа и роли проверит axe и
// проход табом, а вот «бегунок приезжает раньше, чем дорожка договорит» видно
// только глазом.
//
// Проход табом отсюда же: группа сегментов должна быть ОДНОЙ остановкой (внутрь
// водят стрелки), список открываться с клавиатуры, ползунок ходить стрелками и
// Home/End. Если что-то из этого потерялось - переезд не удался, ради этого он
// и был.
import { useState } from "react";

import { Card } from "../card";
import { Icon } from "../icons";
import { Heading, Note } from "../text";
import { FlowInput } from "./input";
import { Segmented, type SegmentedOption } from "./segmented";
import { Select } from "./select";
import { SettingRow } from "../setting-row";
import { Slider } from "./slider";
import { StatRow } from "./stat-row";
import { Toggle, ToggleRow } from "./toggle";

const CLEANUP: SegmentedOption<string>[] = [
  { label: "ничего", value: "none" },
  { label: "слегка", value: "light" },
  { label: "обычно", value: "medium" },
  { label: "сильно", value: "high" },
];

// Значения булевы - так стоит «Термины» в настройках. Проверяем заодно, что
// true и "true" не слиплись по дороге в DOM.
const TERMS: SegmentedOption<boolean>[] = [
  { label: "выключены", value: false },
  { label: "включены", value: true },
];

const LANGS: SegmentedOption<string>[] = [
  { label: "Русский", value: "ru" },
  { label: "English", value: "en" },
];

// Длинное имя нарочно: у микрофонов в Windows они такие, и голова списка
// должна обрезать подпись, а не разъезжаться.
const MICS = [
  { label: "Микрофон (Realtek High Definition Audio)", value: "realtek" },
  { label: "USB-микрофон", value: "usb" },
  { label: "Наушники с микрофоном", value: "headset" },
];

export function FormShowcase() {
  const [keepMic, setKeepMic] = useState(true);
  const [sounds, setSounds] = useState(false);
  const [bare, setBare] = useState(true);
  const [cleanup, setCleanup] = useState("medium");
  const [terms, setTerms] = useState(false);
  const [lang, setLang] = useState("ru");
  const [mic, setMic] = useState("realtek");
  const [preBuffer, setPreBuffer] = useState(0.5);
  const [minRecord, setMinRecord] = useState(0.3);
  const [search, setSearch] = useState("");
  const [url, setUrl] = useState("http://127.0.0.1:11434");

  return (
    <div className="flex flex-col gap-10">
      <Group title="Переключатель">
        <Card>
          <ToggleRow
            first
            icon={<Icon name="history" size={20} />}
            title="Не терять первое слово"
            subtitle="Микрофон наготове, поэтому начало фразы не обрежется"
            checked={keepMic}
            onChange={setKeepMic}
          />
          <ToggleRow
            icon={<Icon name="sound" size={20} />}
            title="Звуковые сигналы"
            subtitle="Тихий щелчок в начале и в конце диктовки"
            more="Слышно только вам: сигнал играет в наушники, а не в микрофон, и в запись не попадает."
            checked={sounds}
            onChange={setSounds}
          />
          <ToggleRow
            title="Недоступно"
            subtitle="Выключенный гаснет целиком и не обещает нажатия курсором"
            checked={false}
            onChange={() => undefined}
            disabled
          />
        </Card>
        <Row label="Сам по себе, без строки">
          <Toggle checked={bare} onChange={setBare} label="Сам по себе" />
        </Row>
      </Group>

      <Group title="Сегменты">
        <Card>
          <SettingRow
            first
            icon={<Icon name="sparkles" size={20} />}
            title="Убирать слова-паразиты"
            subtitle="«Ну вот, короче, я думаю» станет «Я думаю»"
          >
            <Segmented
              options={CLEANUP}
              value={cleanup}
              onChange={setCleanup}
              label="Убирать слова-паразиты"
            />
          </SettingRow>
          <SettingRow
            icon={<Icon name="code" size={20} />}
            title="Термины"
            subtitle="Знает про «эксель», «зум» и ещё сотню слов"
          >
            <Segmented options={TERMS} value={terms} onChange={setTerms} label="Термины" />
          </SettingRow>
          <SettingRow
            icon={<Icon name="languages" size={20} />}
            title="Язык программы"
            subtitle="Меняются подписи в окнах, не распознавание"
          >
            <Segmented options={LANGS} value={lang} onChange={setLang} label="Язык программы" />
          </SettingRow>
          <SettingRow title="Выключенные" subtitle="Стрелки внутрь группы не водят">
            <Segmented
              options={LANGS}
              value={lang}
              onChange={setLang}
              label="Выключенные"
              disabled
            />
          </SettingRow>
        </Card>
        <Note>
          Колонки равной ширины: бегунок ездит сдвигом на целую колонку, и мерить
          подписи не нужно.
        </Note>
      </Group>

      <Group title="Список">
        <Card>
          <SettingRow
            first
            icon={<Icon name="mic" size={20} />}
            title="Микрофон"
            subtitle="Тот, в который вы говорите"
          >
            <Select options={MICS} value={mic} onChange={setMic} label="Микрофон" />
          </SettingRow>
          <SettingRow title="Выключенный" subtitle="Не открывается ни щелчком, ни с клавиатуры">
            <Select
              options={MICS}
              value={mic}
              onChange={setMic}
              label="Выключенный"
              disabled
              className="w-[230px]"
            />
          </SettingRow>
        </Card>
        <Note>
          Набор букв ведёт к пункту, Esc закрывает не выбрав, при открытии список
          прокручивается к выбранному. В QML ничего этого не было.
        </Note>
      </Group>

      <Group title="Ползунок">
        <Card>
          <SettingRow
            first
            icon={<Icon name="timer" size={20} />}
            title="Запас перед нажатием"
            subtitle="Начало фразы не обрежется, даже если вы заговорили раньше клавиши"
          >
            <Slider
              value={preBuffer}
              onChange={setPreBuffer}
              from={0}
              to={1.5}
              step={0.1}
              label="Запас перед нажатием"
            />
          </SettingRow>
          <SettingRow
            icon={<Icon name="gauge" size={20} />}
            title="Записывает само?"
            subtitle="Решает длина нажатия: короче - промах, а не диктовка"
          >
            <Slider
              value={minRecord}
              onChange={setMinRecord}
              from={0.1}
              to={1.5}
              step={0.1}
              label="Записывает само"
            />
          </SettingRow>
          <SettingRow title="Выключенный" subtitle="Ручку не взять, стрелки не двигают">
            <Slider
              value={minRecord}
              onChange={setMinRecord}
              from={0.1}
              to={1.5}
              step={0.1}
              label="Выключенный"
              disabled
            />
          </SettingRow>
        </Card>
      </Group>

      <Group title="Поле ввода">
        <Card>
          <SettingRow
            first
            title="Обычное"
            subtitle="Кольца фокуса нет намеренно: о фокусе говорят курсор и рамка"
          >
            <FlowInput
              value={search}
              onChange={setSearch}
              placeholder="Найти в надиктованном…"
              label="Найти в надиктованном"
            />
          </SettingRow>
          <SettingRow
            icon={<Icon name="link" size={20} />}
            title="Адрес Ollama"
            subtitle="Моноширинное - для того, что не проза"
          >
            <FlowInput
              value={url}
              onChange={setUrl}
              mono
              label="Адрес Ollama"
              className="w-[220px]"
            />
          </SettingRow>
          <SettingRow title="Выключенное" subtitle="Гаснет целиком, курсор обычный">
            <FlowInput value="" onChange={() => undefined} placeholder="Недоступно" disabled />
          </SettingRow>
        </Card>
      </Group>

      <Group title="Строка со статистикой">
        <Card>
          <StatRow
            first
            title="Диктовок"
            subtitle="Сколько раз вы говорили вместо того, чтобы печатать"
            value="128"
          />
          <StatRow title="Наговорено" subtitle="Столько вы говорили" value="2 ч 14 мин" />
          <StatRow
            title="Сэкономлено"
            subtitle="Печатать это руками - примерно 40 слов в минуту. Столько вы сберегли"
            value="1 ч 51 мин"
          />
          <StatRow title="Ваша манера" subtitle="Говорите короткими фразами и по делу" value="" />
        </Card>
        <Note>
          Цифры табличные: числа в столбик выстраиваются по разрядам, и строки не
          пляшут по ширине.
        </Note>
      </Group>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <Heading>{title}</Heading>
      {children}
    </section>
  );
}

/** Контрол сам по себе, без строки настройки: посмотреть на него отдельно. */
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4 px-6">
      <span className="font-sans text-sm text-text-muted">{label}</span>
      {children}
    </div>
  );
}
