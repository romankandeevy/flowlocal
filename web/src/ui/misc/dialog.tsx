// Выплывающая панель прежних версий и фон окна.
//
// Вместе они здесь потому, что обе - слои: одна ложится поверх всего окна,
// другая под всё. Ни та, ни другая не часть страницы.
import * as Dialog from "@radix-ui/react-dialog";

import { Button } from "../button";
import { cn } from "../cn";
import { Icon } from "../icons";
import { SettingRow } from "../setting-row";
import { Heading } from "../text";

export interface VersionEntry {
  /** «0.21», «0.9» - номер по старой схеме. */
  version: string;
  date: string;
  title: string;
  /** Пункты выпуска, как в CHANGELOG.md. */
  items: string[];
}

/**
 * Список прежних версий - архив 0.x из docs/history-0.x.md.
 *
 * Зачем выплывающей панелью, а не страницей. Это редкая справка «как программа
 * дошла до 1.0»: её открывают раз, читают и закрывают. Своего пункта в панели
 * она не заслуживает - всплыть поверх «О программе» и уйти ровно её вес.
 *
 * ---- Почему Radix, а не свой оверлей ----
 *
 * В QML эта панель собрана руками: подложка на всё окно, Rectangle по центру,
 * MouseArea, который ловит клик мимо, и второй MouseArea на самой панели, чтобы
 * клик по ней до подложки не дошёл. Штатный Popup там взять было неоткуда - его
 * плагин не грузится из нашей сборки. И у этой самоделки нет трёх вещей, о
 * которых при ручной сборке просто не вспоминают: таб уходит гулять по окну ПОД
 * панелью, Esc приходится ловить снаружи (Settings.qml делает это за неё,
 * потому что у оверлея нет фокуса), а после закрытия фокус не возвращается
 * туда, откуда панель открыли, - человек с клавиатурой оказывается в начале
 * окна. Radix пишет все три правильно, и переписывать их своими руками во
 * второй раз незачем.
 *
 * Данные приходят пропсом, а не читаются из моста: так панель не привязана к
 * окну, в котором висит, и её можно поднять где угодно.
 */
export function VersionsDialog({
  open,
  onClose,
  title,
  versions,
}: {
  open: boolean;
  /**
   * Закрытие наружу, а не своим состоянием: открытость панели - это флаг окна,
   * и сбрасывать его должен владелец флага. Внутренние действия (клик мимо,
   * Esc, «Закрыть») лишь просят закрыть.
   */
  onClose: () => void;
  title: string;
  /** Пусто - панель и не покажут: кнопку-открывашку прячет тот, у кого список. */
  versions: VersionEntry[];
}) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <Dialog.Portal>
        {/* Подложка гасит окно под собой. Краска - бумага на 92 %, как в QML:
            своих затемнений не заводим, и на тёмной теме подложка темнеет сама
            вместе с токеном. */}
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)]" />
        <Dialog.Content
          // Описание у панели есть, но видеть его незачем: заголовок и так
          // говорит, что это. Без него Radix ругается в консоль, а глушить
          // предупреждение вместо ответа на него - худший из двух вариантов.
          aria-describedby={undefined}
          className={cn(
            "fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
            "flex max-h-[620px] w-[560px] max-w-[calc(100vw-96px)] flex-col",
            "rounded-lg border border-border bg-paper shadow-card",
          )}
        >
          {/* Панель появляется сразу, без проявления. В QML она выплывала за
              180 мс, и повторить это одним transition нельзя: элемент рождается
              уже открытым, переходить не от чего. Ставить ради этого
              @keyframes не стали - справку, которую открывают раз в год, они
              задержали бы на те же 180 мс и ничего бы не объяснили. */}
          <div className="flex h-14 shrink-0 items-center gap-4 border-b border-border pr-4 pl-6">
            <Dialog.Title asChild>
              <h2 className="flex-1 truncate font-sans text-xl font-semibold text-text">
                {title}
              </h2>
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button label="Закрыть" />
            </Dialog.Close>
          </div>

          {/* Прокручиваемая часть обязана быть достижимой с клавиатуры: без
              tabIndex до неё доходят только мышью и колесом, а стрелками -
              никак. */}
          <div className="min-h-0 flex-1 overflow-y-auto py-2" tabIndex={0}>
            {/* Первой строкой - что это за список, чтобы архив не начинался
                сразу с номеров без объяснения. */}
            <Heading className="px-6 pt-3 pb-1">Все выпуски до 1.0</Heading>
            {versions.map((v, i) => (
              <SettingRow
                key={v.version}
                first={i === 0}
                icon={<Icon name="about" />}
                title={`Версия ${v.version}`}
                subtitle={v.title}
                // В QML пункты выпуска склеивались в строку с дефисами и
                // отдавались разметке Markdown. Здесь это настоящий список:
                // диктор говорит «список, пять пунктов», а не читает дефисы.
                more={
                  v.items.length > 0 ? (
                    <ul className="list-disc pl-4">
                      {v.items.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  ) : undefined
                }
              >
                <span className="font-mono text-2xs text-text-muted">
                  {v.date}
                </span>
              </SettingRow>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------

// Фон окна: точечная сетка плюс «прожектор» акцентом сверху.
//
// Не украшательство и не самодеятельность - это tokens/patterns.css из Korti
// (.ins-bg-dots и .ins-bg-spot), там же и объяснено зачем: «subtle, technical
// background textures so surfaces aren't flat/boring». Обе краски выведены из
// ink и accent на низкой прозрачности, поэтому инвертируются вместе с темой.
//
// Значения - из первоисточника, не на глаз:
//   точки     - radial ink/0.10, шаг 20
//   прожектор - radial(60% 55% at 50% -5%, --accent-bg, transparent 70%)
//   --accent-bg = accent/0.10 светлая, accent/0.16 тёмная
//   к краям всё гаснет маской (radial 120% 90% at 50% 0%)
//
// В QML всё это рисовал Canvas по точке за раз: QtQuick.Effects тянет
// Qt6QuickEffects.dll, который без ручного подъёма не грузится. Оттуда же и
// упрощения - круглый градиент вместо эллипса и линейное затухание вместо
// маски. Браузеру ничего этого не нужно: тут и эллипс, и настоящая маска
// берутся из первоисточника как есть, и рисуется фон нулём наших строк на кадр.

// Прожектор. Долей две, а не одна: у тёмной темы --accent-bg своя, и это не
// небрежность системы, а выправленный контраст. Переопределение висит на
// :root[data-theme=dark] - тему ставит Python атрибутом на <html>.
const SPOT =
  "bg-[radial-gradient(60%_55%_at_50%_-5%,color-mix(in_srgb,var(--color-accent)_10%,transparent),transparent_70%)]";
const SPOT_DARK =
  "[:root[data-theme=dark]_&]:bg-[radial-gradient(60%_55%_at_50%_-5%,color-mix(in_srgb,var(--color-accent)_16%,transparent),transparent_70%)]";

// Сетка. Точка радиусом 1 с шагом 20 - один повторяющийся градиент вместо
// полутора тысяч кругов, которые Canvas обходил в цикле.
const DOTS = cn(
  "bg-[radial-gradient(circle,color-mix(in_srgb,var(--color-ink)_10%,transparent)_1px,transparent_1px)]",
  "[background-size:20px_20px]",
  // Маска гасит сетку к краям, чтобы она не спорила с содержимым внизу
  // длинных страниц.
  "[mask-image:radial-gradient(120%_90%_at_50%_0%,#000,transparent)]",
);

/**
 * Фон окна. Ставится один раз на всё окно, ниже содержимого.
 *
 * fixed, а не absolute: фон не должен уезжать при прокрутке страницы - в QML
 * прокручивается содержимое внутри Flickable, а фон стоит на месте. Краску
 * бумаги под ним кладёт body (index.css), второй раз её класть незачем.
 */
export function Backdrop({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("pointer-events-none fixed inset-0 -z-10", className)}
    >
      <div className={cn("absolute inset-0", SPOT, SPOT_DARK)} />
      <div className={cn("absolute inset-0", DOTS)} />
    </div>
  );
}
