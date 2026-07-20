// Сочетание клавиш плашками: [Ctrl] + [Shift] + [Space].
//
// Приём - из мастера первого запуска: заливка --fill-subtle, волосяная линия,
// радиус 6, моноширинный шрифт. Сочетание клавиш - голос терминала, и в
// системе оно всегда набрано моноширинным.
//
// Разница с мастером одна, и она по назначению. Там это ОДНО поле на всё
// сочетание, потому что в него жмут: поле должно выглядеть полем. Здесь его
// читают, а не нажимают, поэтому клавиши разнесены по штуке - так строка
// перестаёт быть текстом и становится картинкой клавиатуры, которую видно
// боковым зрением.
//
// Перенос по словам обязателен: содержимому главного окна достаётся 420
// пикселей, и «Ctrl + Alt + Shift + Space» должно переноситься само, а не
// уезжать за край.

import { cn } from "../cn";

export interface KeyCapsProps {
  /**
   * Готовая строка от inputspec.pretty: «Ctrl + Shift + Space». Разбираем её
   * сами, а не просим Python отдать список: склеивает эти куски тоже inputspec,
   * и второго мнения о разделителе в программе быть не должно - поменяется
   * там, поменяется и здесь.
   */
  combo: string;
  /** Кегль надписи на клавише. Высота плашки считается от него. */
  keySize?: number;
  /**
   * Какие плашки зажаты прямо сейчас - по индексу. Пустой массив значит «никто
   * не жмёт». Нужно мастеру первого запуска: там человек первый раз в жизни
   * жмёт это сочетание и должен увидеть, что программа его слышит, а не
   * поверить на слово.
   */
  down?: boolean[];
  /**
   * Сочетание собрано целиком. Цвет тут зелёный, а не синий, и это не выбор на
   * глаз: в системе зелёный - «работает, в эфире» (им же горит точка записи на
   * пилюле), а синий - «фокус, выделение». Нажатое сочетание первое, а не
   * второе.
   */
  lit?: boolean;
  className?: string;
}

export function KeyCaps({
  combo,
  keySize = 15,
  down = [],
  lit = false,
  className,
}: KeyCapsProps) {
  const parts = combo ? combo.split(" + ") : [];
  const capH = keySize + 20;

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {parts.map((part, i) => {
        // `down` короче parts или пуст - получаем undefined, и сравнение с true
        // честно даёт false.
        const held = down[i] === true;
        return (
          // Плюс едет вместе со своей клавишей, а не отдельным элементом
          // строки: при переносе он обязан уйти на новую строку с ней, иначе
          // строка закончится висящим «+».
          <span key={`${part}-${i}`} className="flex items-center gap-2">
            {i > 0 ? (
              <span
                className="flex items-center font-sans text-sm text-text-faint"
                style={{ height: capH }}
              >
                +
              </span>
            ) : null}
            <span
              className={cn(
                "flex items-center justify-center rounded-sm border px-[11px]",
                "font-mono font-medium",
                "transition-[background-color,border-color,color,transform]",
                "duration-[var(--dur-fast)] ease-out",
                lit
                  ? "border-success text-success"
                  : held
                    ? "border-border-strong bg-fill-strong text-text"
                    : "border-border bg-fill-subtle text-text",
                // Масштаб, а не сдвиг вниз: клавиша должна утонуть под пальцем,
                // но раскладка считается по геометрии детей, и подвинутая
                // плашка потащила бы за собой всю строку. Масштаб на раскладку
                // не влияет вовсе.
                held && !lit && "scale-[0.96]",
              )}
              style={{
                height: capH,
                fontSize: keySize,
                ...(lit
                  ? {
                      background:
                        "color-mix(in srgb, var(--color-success) 12%, transparent)",
                    }
                  : null),
              }}
            >
              {part}
            </span>
          </span>
        );
      })}
    </div>
  );
}
