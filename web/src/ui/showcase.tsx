// Витрина контролов. Это не окно программы, а выкладка деталей: посмотреть
// глазами на краски, отступы и отклик до того, как из них собрано окно.
//
// Критерий фазы 3 проверяется прямо здесь: все компоненты, обе темы, проход
// табом, axe-core без нарушений. Переключатели темы и раскладки сверху -
// чтобы не пересобирать ради этого страницу.
//
// Разделы лежат отдельными файлами и подключаются сюда. Так их можно писать
// параллельно, не толкаясь в одном файле.
import { useEffect, useState } from "react";

import { Button } from "./button";
import { Card } from "./card";
import { cn } from "./cn";
import { FormShowcase } from "./form/showcase";
import { IconsShowcase } from "./icons.showcase";
import { LayoutModeProvider, type LayoutMode } from "./layout-mode";
import { SettingRow } from "./setting-row";
import { Heading, Note } from "./text";

type Theme = "light" | "dark";

export function Showcase() {
  const [theme, setTheme] = useState<Theme>("light");
  const [layout, setLayout] = useState<LayoutMode>("cards");

  // Тему ставим атрибутом на <html> - ровно так, как её будет ставить Python
  // через runJavaScript. Не prefers-color-scheme: тему выбирают в настройках
  // программы, а системная там лишь один вариант из трёх.
  useEffect(() => {
    document.documentElement.dataset["theme"] = theme;
  }, [theme]);

  return (
    <LayoutModeProvider mode={layout}>
      <div className="min-h-screen bg-bg">
        <header
          className={cn(
            "sticky top-0 z-10 flex flex-wrap items-center gap-3",
            "border-b border-border bg-bg/90 px-8 py-4 backdrop-blur",
          )}
        >
          <Heading level="page" className="mr-auto">
            Витрина
          </Heading>
          <Button
            label={theme === "light" ? "Тёмная тема" : "Светлая тема"}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          />
          <Button
            label={layout === "cards" ? "Линиями" : "Карточками"}
            onClick={() => setLayout(layout === "cards" ? "lines" : "cards")}
          />
        </header>

        <main className="mx-auto flex max-w-[640px] flex-col gap-10 px-8 py-10">
          <Section title="Кнопки">
            <Card>
              <SettingRow
                first
                title="Три вида"
                subtitle="Основная, обычная и опасная. Ступени отклика одни и те же."
              >
                <div className="flex gap-2">
                  <Button kind="primary" label="Сохранить" />
                  <Button label="Отмена" />
                  <Button kind="danger" label="Удалить" />
                </div>
              </SettingRow>
              <SettingRow
                title="Выключенная"
                subtitle="Гаснет целиком и не обещает нажатия курсором."
              >
                <Button label="Недоступно" disabled />
              </SettingRow>
            </Card>
          </Section>

          <Section title="Строка настройки">
            <Card>
              <SettingRow
                first
                title="Без иконки"
                subtitle="Подпись занимает всю ширину ряда, а не остаток справа."
              >
                <Button label="Кнопка" />
              </SettingRow>
              <SettingRow
                title="С раскрытием"
                subtitle="Короткая подпись отвечает на «что мне это даст»."
                more="Длинное объяснение живёт под шевроном и открывается с клавиатуры само - это <details>, а не двадцать строк своего кода. Диктор объявляет его раскрывающимся."
              >
                <Button label="Кнопка" />
              </SettingRow>
              <SettingRow
                title="Без контрола"
                subtitle="Бывает и так: строка только рассказывает."
              />
            </Card>
            <Note>
              Пояснение под карточкой. Тише текста, но не шёпотом.
            </Note>
          </Section>

          <Section title="Формы">
            <FormShowcase />
          </Section>

          <Section title="Иконки">
            <IconsShowcase />
          </Section>
        </main>
      </div>
    </LayoutModeProvider>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <Heading>{title}</Heading>
      {children}
    </section>
  );
}
