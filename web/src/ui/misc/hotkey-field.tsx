// Поле «нажмите сочетание».
//
// ---- Захвата тут нет и не будет ----
//
// Само сочетание ловит Python (Backend.startCapture, хук keyboard), и это не
// временное положение дел, а единственно возможное. Браузеру Win не отдают
// вовсе, а перехват сочетаний внутри вебвью не работает: половина комбинаций
// уходит системе или самому окну раньше, чем до страницы доходит событие.
// Ловить надо ещё и боковые кнопки мыши, которых у клавиатурных событий нет.
// Плюс имена клавиш обязаны совпадать с теми, которыми приложение вешает
// хоткей: разойдись поле и хук в понимании слова «ctrl» - и получится баг,
// который здесь уже был.
//
// Поэтому компонент только ПОКАЗЫВАЕТ: текущее сочетание и состояние «жду
// нажатия». Начало и конец захвата - вызовы моста, а моста ещё нет, отсюда
// пропсы value/capturing и обработчики наружу. Когда мост появится, HotkeyField
// перестанет принимать value и capturing и начнёт читать их сам.
import { cn } from "../cn";

export function HotkeyBox({
  value,
  capturing = false,
  allowClear = false,
  keyStart = true,
  disabled = false,
  onStartCapture,
  onCancelCapture,
  onClear,
}: {
  /**
   * Человекочитаемое сочетание - «Ctrl + Shift + Space». Уже собранное, а не
   * запись из конфига: склеивает куски inputspec на стороне Python, и второго
   * мнения о разделителе в программе быть не должно. Пусто - «не назначено».
   */
  value: string;
  /** Захват идёт прямо сейчас: Python ждёт нажатия. */
  capturing?: boolean;
  /** Показывать крестик: «выключено» - законное состояние для необязательного. */
  allowClear?: boolean;
  /**
   * Начинать ли захват с клавиатуры. По умолчанию да - так поле доступно и без
   * мыши. Выключается на экранах мастера: там человек НАЖИМАЕТ сочетание ради
   * живой проверки, а пробел входит в стандартное ctrl+shift+space - и «Space
   * начинает захват» превращал каждую проверку в переназначение. Захват дрался
   * с проверкой и шёл по кругу, «Дальше» не открывалась.
   */
  keyStart?: boolean;
  disabled?: boolean;
  onStartCapture?: () => void;
  onCancelCapture?: () => void;
  onClear?: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={disabled}
        // Пока ждём нажатия, поле объявляет себя нажатым: диктор говорит
        // «нажато», и состояние «жду» слышно, а не только видно.
        aria-pressed={capturing}
        onClick={() => (capturing ? onCancelCapture?.() : onStartCapture?.())}
        onKeyDown={(e) => {
          // Space и Enter нажимают <button> сами - в QML под это написан
          // отдельный разбор клавиш. Здесь остаётся ровно два случая, которых
          // у кнопки нет своих.
          if (!keyStart && (e.key === " " || e.key === "Enter")) {
            e.preventDefault();
            return;
          }
          if (e.key === "Escape" && capturing) {
            e.preventDefault();
            onCancelCapture?.();
          }
        }}
        className={cn(
          "h-[34px] w-[200px] cursor-pointer truncate rounded-sm border px-2.5",
          // Моноширинный: сочетание клавиш - это голос терминала.
          "font-mono text-2xs",
          "transition-[background-color,border-color,color,opacity]",
          "duration-[var(--dur-fast)] ease-out",
          "disabled:cursor-default disabled:opacity-40",
          capturing
            ? // Синий - только особенное: захват это фокус, ровно его случай.
              cn(
                "border-accent text-accent",
                "bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)]",
              )
            : cn(
                "border-border bg-fill-subtle",
                value ? "text-text" : "text-text-faint",
                "enabled:hover:border-border-strong enabled:hover:bg-fill",
              ),
        )}
      >
        {capturing ? "нажмите сочетание…" : value || "не назначено"}
      </button>

      {allowClear && value ? (
        <button
          type="button"
          onClick={onClear}
          aria-label="Убрать сочетание"
          className={cn(
            // Подложка под крестиком: без неё цель клика в 20 пикселей ничем
            // не обозначена, и наведение читается как случайное покраснение
            // значка.
            "flex size-5 cursor-pointer items-center justify-center rounded-sm",
            "text-2xs text-text-faint",
            "transition-colors duration-[var(--dur-fast)] ease-out",
            "hover:bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)]",
            "hover:text-danger",
            "active:bg-[color-mix(in_srgb,var(--color-danger)_18%,transparent)]",
          )}
        >
          <span aria-hidden="true">✕</span>
        </button>
      ) : null}
    </div>
  );
}

/**
 * HotkeyBox, привязанный к ключу конфига.
 *
 * Вся его работа - помнить, какой это ключ, и подставлять его в вызовы наружу.
 * В QML этот же файл читал `B.get(field)` и слушал сигнал `captureDone`,
 * отсеивая чужие поля по имени; когда мост появится, это вернётся сюда, и
 * пропсы value/capturing уйдут - страница перестанет держать чужое состояние.
 * Пока моста нет, обёртка избавляет страницу хотя бы от замыканий на каждое из
 * восьми полей.
 */
export function HotkeyField({
  field,
  value,
  capturing = false,
  allowClear = false,
  keyStart = true,
  disabled = false,
  onStartCapture,
  onCancelCapture,
  onClear,
}: {
  /** Ключ конфига: «hotkey_hold», «hotkey_toggle» и прочие. */
  field: string;
  value: string;
  capturing?: boolean;
  allowClear?: boolean;
  keyStart?: boolean;
  disabled?: boolean;
  onStartCapture?: (field: string) => void;
  onCancelCapture?: (field: string) => void;
  onClear?: (field: string) => void;
}) {
  return (
    <HotkeyBox
      value={value}
      capturing={capturing}
      allowClear={allowClear}
      keyStart={keyStart}
      disabled={disabled}
      onStartCapture={() => onStartCapture?.(field)}
      onCancelCapture={() => onCancelCapture?.(field)}
      onClear={() => onClear?.(field)}
    />
  );
}
