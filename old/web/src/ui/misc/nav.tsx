// Боковое меню и вордмарк - две детали оболочки окна.
//
// Обе по канону Korti (templates/app-shell), обе стоят в нескольких местах, и
// обе обязаны совпадать между этими местами: вордмарк, нарисованный трижды на
// глаз, расходится на первой же правке.
import { cn } from "../cn";
import { Icon, type IconName } from "../icons";

/**
 * Пункт бокового меню: знак плюс подпись. Активный - заливка fill и чернила,
 * остальные - text-secondary.
 *
 * Синим не красим: акцент в системе для особенного (фокус, ссылки), а не для
 * «тут я сейчас».
 *
 * Здесь <button> вместо Item с MouseArea, и это не косметика. В QML пункт
 * разбирал Space и Enter вручную, держал своё поле `mouseFocus`, чтобы кольцо
 * фокуса не загоралось от щелчка мышью, и рисовал это кольцо отдельным
 * контролом. Всё три вещи браузер делает сам: :focus-visible уже знает, что
 * фокус от мыши подсвечивать не надо. Сверх того появилось aria-current -
 * диктор говорит «текущая страница», а в QML активный пункт отличался только
 * краской, то есть на слух не отличался никак.
 */
export function NavItem({
  label,
  icon,
  active = false,
  onClick,
}: {
  label: string;
  icon?: IconName;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-[34px] w-full cursor-pointer items-center gap-3 rounded-sm px-3",
        "text-left font-sans text-md font-medium",
        "transition-colors duration-[var(--dur-fast)] ease-out",
        active
          ? "bg-fill text-text"
          : "text-text-secondary hover:bg-fill-subtle active:bg-fill",
      )}
    >
      {icon ? (
        // Знак тише подписи, пока пункт не выбран. Цвет идёт через
        // currentColor обёртки - сама иконка о теме не знает ничего.
        <span className={cn("shrink-0", !active && "text-text-muted")}>
          <Icon name={icon} size={17} />
        </span>
      ) : null}
      <span className="min-w-0 truncate">{label}</span>
    </button>
  );
}

// Два размера вместо произвольного числа. В QML сторона квадрата и кегль имени
// задавались числами на месте постановки, и на странице «О программе» знак
// заметно висел выше имени - поправку приходилось считать заново под каждый
// размер. Здесь размеров ровно два, оба выверены, и третьего не бывает.
const SIZES = {
  // Шапка главного окна и боковая панель настроек.
  md: {
    box: "size-7",
    name: "text-xl",
    icon: 16,
    // Оптическая центровка знака, и она замерена, а не на глаз. По геометрии
    // микрофон стоит ровно, но у иконки Lucide тяжёлая часть - дуга под
    // капсулой, она идёт во всю ширину ниже середины, и глаз читает знак
    // съехавшим вниз. Подъём - около 4.5 % от стороны квадрата.
    lift: "-translate-y-px",
  },
  // «О программе»: там вордмарк работает заголовком страницы.
  lg: { box: "size-[34px]", name: "text-display", icon: 19, lift: "-translate-y-0.5" },
} as const;

/**
 * Знак плюс имя. Квадрат со скруглением, внутри знак чернилами по бумаге,
 * справа имя дисплейным весом с тесным трекингом. У Korti знак - буква «i», у
 * нас микрофон: то, чем занят продукт.
 *
 * Имя набрано <span>, а не заголовком: на всех трёх страницах, где вордмарк
 * стоит, свой заголовок уже есть, и второй h1 рядом с ним - это два названия
 * у одной страницы для того, кто слушает.
 */
export function Wordmark({
  size = "md",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const s = SIZES[size];
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-sm bg-ink text-bg",
          s.box,
        )}
      >
        <Icon name="mic" size={s.icon} strokeWidth={2.2} className={s.lift} />
      </span>
      <span
        className={cn(
          // Вес 700, а не 800: Onest в ExtraBold заметно чернее оригинала.
          // Трекинг -.03em, как у дисплейных кеглей в системе, и задан в em, а
          // не пикселями - это приём, а не число: на другом кегле пиксели
          // молча становятся неправдой.
          "font-sans font-bold tracking-[-0.03em] text-text",
          s.name,
        )}
      >
        FlowLocal
      </span>
    </div>
  );
}
