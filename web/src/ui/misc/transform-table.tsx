// Свои преобразования: «название» и «что сделать с текстом».
//
// Похоже на PairTable, но не она. Там слева ключ, справа значение, и обе
// стороны короткие; здесь справа - фраза, которую человек пишет словами, и поле
// под неё нужно втрое шире. Разводить одну таблицу параметрами вышло бы дороже,
// чем написать вторую: сюда ещё придёт ограничение на количество и подсказка
// про указание, а туда - нет.
//
// Указание уходит в модель как есть. Это единственное место в программе, где
// человек говорит с моделью напрямую, и переписывать его формулировку под наш
// формат мы не будем: он лучше знает, чего хочет.
//
// Разметка - настоящая <table> со спрятанными <th>, ровно по тем же доводам,
// что расписаны в шапке pair-table.tsx.
import { Button } from "../button";
import { Card } from "../card";
import { EmptyState } from "./empty-state";
import { TableInput } from "./pair-table";

export interface Transform {
  /** Как называется в списке, который выбирают цифрой. */
  title: string;
  /** Что сделать с выделенным текстом - словами, как объяснили бы человеку. */
  instruction: string;
}

/**
 * Сколько строк не сохранится. Правило другое, чем у подстановок: там довольно
 * ключа, здесь нужны обе половины - преобразование без указания не сделает
 * ничего, а без названия его не выбрать.
 */
export function countTransformBlanks(rows: Transform[]): number {
  return rows.filter(
    (r) => r.title.trim() === "" || r.instruction.trim() === "",
  ).length;
}

export function TransformTable({
  rows,
  onChange,
}: {
  rows: Transform[];
  onChange: (next: Transform[]) => void;
}) {
  function edit(i: number, patch: Partial<Transform>) {
    const next = rows.map((r) => ({ ...r }));
    const cur = next[i];
    if (!cur) return;
    next[i] = { ...cur, ...patch };
    onChange(next);
  }

  // Серая строчка «своих пока нет» была честной, но неотличимой от пустого
  // поля: на свежей установке своих преобразований нет ни у кого, и первое, что
  // человек здесь видел, - пустая карточка.
  //
  // Пустое состояние тут ВНУТРИ таблицы, в отличие от подстановок. Разница не в
  // непоследовательности: у подстановок пустая карточка сменяется живой строкой
  // с полями, и объяснять надо до формы; здесь сменять нечем - пока своих нет,
  // на месте таблицы нет вообще ничего.
  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="sparkles"
          title="Своих преобразований пока нет"
          hint="Нажмите «Добавить»: слева название, справа - что сделать с выделенным текстом."
        />
      </Card>
    );
  }

  return (
    <Card>
      <div className="px-6 pt-3.5 pb-1.5">
        <table className="w-full table-fixed">
          <caption className="sr-only">Свои преобразования</caption>
          <colgroup>
            <col className="w-[170px]" />
            <col />
            <col className="w-20" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="sr-only">
                Название
              </th>
              <th scope="col" className="sr-only">
                Что сделать с текстом
              </th>
              <th scope="col" className="sr-only">
                Действие
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              // Индекс ключом - здесь это верно, а не лень: строки правят на
              // месте, и ключ из содержимого менялся бы на каждой набранной
              // букве, то есть поле теряло бы фокус посреди слова.
              <tr key={i}>
                <td className="pr-2 pb-2">
                  <TableInput
                    value={row.title}
                    label="Название"
                    placeholder="По-деловому"
                    onChange={(t) => edit(i, { title: t })}
                  />
                </td>
                <td className="pr-2 pb-2">
                  <TableInput
                    value={row.instruction}
                    label="Что сделать с текстом"
                    placeholder="Перепиши вежливо и по делу, ничего не выбрасывая"
                    onChange={(t) => edit(i, { instruction: t })}
                  />
                </td>
                <td className="pb-2">
                  <Button
                    onClick={() => onChange(rows.filter((_, j) => j !== i))}
                    className="w-full"
                  >
                    Убрать
                    <span className="sr-only">
                      : {row.title || "пустая строка"}
                    </span>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// Свойства `limit` и `full` из QML сюда не переехали намеренно. Обе величины
// нужны кнопке «Добавить» и предупреждению «больше не поместится», а живут они
// на странице, снаружи карточки: кнопку «Добавить» вынесли в заголовок раздела
// ещё в QML - внутри карточки она налезала на «Убрать» первой строки. Таблице
// от этих двух чисел никакой пользы, она бы только вернула их обратно.
// Ограничение приходит из Python (Backend.maxTransforms = transforms.MAX_CUSTOM)
// и означает «больше не влезет в список, который выбирают цифрой с клавиатуры».
