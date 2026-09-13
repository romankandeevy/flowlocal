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

// Холста в jsdom нет: getContext("2d") возвращает null и печатает
// «Not implemented». Волна микрофона это переживает - рисование просто
// пропускается, - но вывод тестов забивается шумом, а шум прячет настоящее.
//
// Заглушка молчаливая и ничего не рисует, и это правда: проверять в jsdom
// нечего - ни раскладки, ни пикселей там нет. Как выглядит волна, видно
// только глазами на витрине.
if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = (() => {
    const noop = () => {};
    const ctx = new Proxy(
      { canvas: null, fillStyle: "", strokeStyle: "", lineWidth: 1 },
      { get: (t, k) => (k in t ? (t as never)[k] : noop), set: () => true },
    );
    return () => ctx;
  })() as unknown as typeof HTMLCanvasElement.prototype.getContext;
}
