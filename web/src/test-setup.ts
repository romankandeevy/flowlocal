// Общая подготовка тестов: матчеры вроде toBeInTheDocument.
import "@testing-library/jest-dom/vitest";

// ResizeObserver в jsdom нет, а Radix им меряет ручку ползунка и положение
// выпадающего списка. Без заглушки витрина с формами падает в тестах, хотя в
// WebView2 объект родной и всё работает. Дыра чисто тестовая, и затыкать её
// надо здесь, а не калечить ради jsdom рабочий код.
//
// Заглушка молчаливая: измерений она не даёт, и это правда - в jsdom нет ни
// раскладки, ни размеров. Тесты здесь про роли и доступность, а не про
// геометрию; геометрию проверяют глазами на витрине.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}
