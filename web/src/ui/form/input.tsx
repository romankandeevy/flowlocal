// Поле ввода: высота 30, радиус 6, линия вместо заливки.
// Фокус - синий акцент: это ровно тот случай, для которого он в системе и
// заведён (фокус, ссылки, выделение), а не «включено».
//
// Кольца фокуса тут нет намеренно, и это единственный контрол-исключение.
// О фокусе в поле говорят мигающий курсор внутри и акцентная рамка - третий
// признак того же события лишний. Довод переносится в веб без правок и даже
// становится сильнее: кольцо зажигается только по :focus-visible, то есть
// только от клавиатуры, а в поле приходят и мышью, и табом одинаково часто -
// значит, оно рисовало бы два разных вида одного состояния. Акцентная рамка
// встаёт одинаково в обоих случаях, поэтому её и оставляем единственной.
//
// Что досталось даром против QML. Там ховер ловится отдельной MouseArea
// поверх поля (TextInput сам hoverEnabled не умеет), и ей обязательно надо
// ставить acceptedButtons: NoButton - иначе она съедала щелчки вместе с
// установкой курсора и выделением мышью. Здесь ховер - это :hover на самом
// поле, и съесть ему нечего.
import { cn } from "../cn";

export function FlowInput({
  value,
  onChange,
  placeholder,
  mono = false,
  disabled = false,
  id,
  label,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Моноширинный: для путей, адресов и прочего, что не проза. */
  mono?: boolean;
  disabled?: boolean;
  id?: string;
  /** Имя для экранного диктора, когда рядом нет своей подписи. */
  label?: string;
  className?: string;
}) {
  return (
    <input
      type="text"
      id={id}
      aria-label={label}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-[30px] w-[200px] rounded-sm border border-border bg-fill-subtle px-3",
        "text-text placeholder:text-text-faint",
        "transition-[background-color,border-color,opacity]",
        "duration-[var(--dur-fast)] ease-out",
        // Ховер поднимает заливку на ступень: без него поле неотличимо от
        // подписи рядом, пока в него не ткнёшь. На поле в фокусе не поднимаем -
        // там уже говорит рамка.
        "hover:border-border-strong hover:bg-fill",
        "focus:border-accent focus:bg-fill-subtle focus:outline-none",
        "disabled:cursor-default disabled:opacity-40",
        mono ? "font-mono text-2xs" : "font-sans text-sm",
        className,
      )}
    />
  );
}
