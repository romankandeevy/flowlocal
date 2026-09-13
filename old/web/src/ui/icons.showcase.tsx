// Витрина набора иконок: все иконки разом, обе темы, обе карты имён.
//
// Зачем страница, а не тест. Про иконку нельзя написать проверку «нарисована
// правильно»: путь либо есть, либо нет, а вот перепутанные местами «Слова» и
// «Дополнительно» или иконка, которая на 14 пикселях слипается в кляксу, видны
// только глазом. Числа и полноту переноса сверяет tools/check_icons.py, а
// сюда смотрят.
//
// Стили здесь только структурные, инлайном. Токены Korti приезжают в
// web/src/theme.css из theme.py, но витрина не должна ломаться от того, что
// классов ещё нет: цвет она берёт из currentColor, фон - от страницы, а
// разделители мешает из currentColor через color-mix. Своих красок не
// заводит - их и нельзя.

import { useState } from "react";

import { ICON_NAMES, Icon, PAGE_ICONS, TRANSFORM_ICONS, type IconName } from "./icons";

/** Линия и подложка одного тона: разбавленный currentColor, а не своя краска. */
const HAIRLINE = "1px solid color-mix(in srgb, currentColor 14%, transparent)";

function useRootTheme(): [string, (next: string) => void] {
  // Тему держит атрибут на <html> - так её ставит Python через runJavaScript
  // при retheme(). Переключаем ровно то же место, а не обёртку вокруг витрины:
  // селектор тёмной темы в theme.css привязан к корню, и на обёртке он бы
  // просто не сработал.
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme ?? "light",
  );
  return [
    theme,
    (next: string) => {
      document.documentElement.dataset.theme = next;
      setTheme(next);
    },
  ];
}

function Cell({ name }: { name: IconName }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        padding: "14px 6px",
        border: HAIRLINE,
        borderRadius: 8,
        minWidth: 0,
      }}
    >
      <Icon name={name} size={24} />
      <span
        style={{
          fontSize: 11,
          opacity: 0.6,
          maxWidth: "100%",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={name}
      >
        {name}
      </span>
    </div>
  );
}

function Row({ label, name }: { label: string; name: IconName | undefined }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 0",
        borderTop: HAIRLINE,
      }}
    >
      {name ? <Icon name={name} /> : <span style={{ width: 17 }} />}
      <span style={{ fontSize: 13 }}>{label}</span>
      <span style={{ fontSize: 11, opacity: 0.5, marginLeft: "auto" }}>{name ?? "-"}</span>
    </div>
  );
}

function Heading({ text }: { text: string }) {
  return (
    <h2 style={{ fontSize: 13, fontWeight: 600, opacity: 0.7, margin: "28px 0 10px" }}>
      {text}
    </h2>
  );
}

export function IconsShowcase() {
  const [theme, setTheme] = useRootTheme();
  const dark = theme === "dark";

  return (
    <div style={{ padding: 24, maxWidth: 880, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 17, fontWeight: 600, margin: 0 }}>Иконки</h1>
        <span style={{ fontSize: 13, opacity: 0.6 }}>{ICON_NAMES.length} шт.</span>
        <button
          type="button"
          onClick={() => setTheme(dark ? "light" : "dark")}
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            fontSize: 13,
            color: "inherit",
            background: "transparent",
            border: HAIRLINE,
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          <Icon name={dark ? "palette" : "moon"} />
          {dark ? "Светлая" : "Тёмная"}
        </button>
      </div>

      {/* Размеры одной строкой: на 14 штрих 1.9 уже толстоват, и это надо
          видеть до того, как размер разойдётся по страницам. */}
      <Heading text="Размеры" />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 20 }}>
        {[14, 17, 20, 24, 32].map((size) => (
          <div key={size} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <Icon name="settings" size={size} />
            <span style={{ fontSize: 11, opacity: 0.5 }}>{size}</span>
          </div>
        ))}
      </div>

      <Heading text="Весь набор" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(104px, 1fr))",
          gap: 8,
        }}
      >
        {ICON_NAMES.map((name) => (
          <Cell key={name} name={name} />
        ))}
      </div>

      {/* Карты показываем ровно так, как их видит человек: подпись слева,
          иконка перед ней. Перепутанные строки здесь заметны сразу. */}
      <Heading text="Страницы" />
      <div>
        {Object.keys(PAGE_ICONS).map((page) => (
          <Row key={page} label={page} name={PAGE_ICONS[page]} />
        ))}
      </div>

      <Heading text="Готовые преобразования" />
      <div>
        {Object.keys(TRANSFORM_ICONS).map((id) => (
          <Row key={id} label={id} name={TRANSFORM_ICONS[id]} />
        ))}
      </div>
    </div>
  );
}

export default IconsShowcase;
