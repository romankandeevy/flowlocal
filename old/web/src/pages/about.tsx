// Страница «О программе»: витрина, обещания, свои данные и служебные двери.
//
// **Ключей конфига у неё нет ни одного, и это меняет способ проверки.** Первый
// критерий фазы 4 - «дампы config.json совпали» - на этой странице не значит
// ровно ничего: её можно перенести пустой, и сверка пройдёт молча. Всё держится
// на втором критерии, то есть на списке вызовов Backend из описи. Их одиннадцать
// (docs/settings-inventory.md), и каждый должен делать то же, что в QML:
//
//   about, changelog, dropRecording, exportData, importData, openConfig,
//   openFolder, openLog, redoRecording, restartOnboarding, savedRecordings
//
// Двенадцатым идёт oldVersions: в QML он читается окном (Settings.qml:110), а не
// страницей, поэтому в опись не попал. Панель прежних версий открывается отсюда,
// значит и список читаем здесь - иначе кнопка осталась бы без данных.
import { useEffect, useState } from "react";

import {
  about,
  changelog,
  dropRecording,
  exportData,
  importData,
  oldVersions,
  on,
  openConfig,
  openFolder,
  openLog,
  redoRecording,
  restartOnboarding,
  savedRecordings,
} from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Icon } from "../ui/icons";
import { VersionsDialog, type VersionEntry } from "../ui/misc/dialog";
import { SettingRow } from "../ui/setting-row";
import { Heading } from "../ui/text";

/** Выпуск в списке «Как обновлялось». */
interface Release extends VersionEntry {
  /** Эта версия стоит у человека прямо сейчас. */
  current: boolean;
}

/** Запись, которую не удалось распознать. */
interface Kept {
  path: string;
  name: string;
  note: string;
}

/**
 * Пункт выпуска с полужирным зачином.
 *
 * Пункты в CHANGELOG.md пишутся как «**Что изменилось.** дальше подробности», и
 * зачин полужирным - не украшение: по нему список просматривают глазами, не
 * читая целиком. В QML под это включался Text.MarkdownText; здесь хватает
 * разреза по звёздочкам, потому что во всём файле встречается ровно эта одна
 * разметка. Тянуть ради неё разбор Markdown значило бы положить в бандл
 * библиотеку на один приём.
 */
function withLead(s: string) {
  return s
    .split("**")
    .map((part, i) =>
      i % 2 === 1 ? (
        <strong key={i} className="font-semibold">
          {part}
        </strong>
      ) : (
        part
      ),
    );
}

export function AboutPage() {
  const [info, setInfo] = useState("");
  const [releases, setReleases] = useState<Release[]>([]);
  const [old, setOld] = useState<VersionEntry[]>([]);
  const [kept, setKept] = useState<Kept[]>([]);
  const [showOld, setShowOld] = useState(false);

  useEffect(() => {
    void about().then((v) => setInfo(String(v ?? "")));
    void changelog().then((v) => setReleases(((v as Release[] | null) ?? [])));
    void oldVersions().then((v) => setOld(((v as VersionEntry[] | null) ?? [])));
  }, []);

  useEffect(() => {
    const load = () => {
      void savedRecordings().then((v) => setKept(((v as Kept[] | null) ?? [])));
    };
    load();
    // Список несохранённых меняется от наших же кнопок: dropRecording шлёт
    // changed, распознавание - тоже. Без подписки строка оставалась бы на
    // экране после удаления до закрытия окна.
    return on("changed", load);
  }, []);

  return (
    <>
      <Heading level="page">{t("О программе")}</Heading>

      <Card>
        <div className="flex flex-col gap-3 px-6 pt-4 pb-4">
          {/* Тот же вордмарк, что на панели, только крупнее: это витрина
              продукта, а не строка меню. Знак приподнят на пару процентов от
              своего размера - оптическая центровка, и она замерена: по
              геометрии микрофон стоит ровно, но тяжёлая дуга под капсулой идёт
              во всю ширину ниже середины, и глаз читает знак съехавшим вниз. */}
          <div className="flex items-center gap-3">
            <span className="flex size-[34px] shrink-0 items-center justify-center rounded-sm bg-primary text-primary-fg">
              <Icon name="mic" size={19} strokeWidth={2.2} className="-translate-y-[2px]" />
            </span>
            <span className="font-sans text-display font-bold tracking-[-0.03em] text-text">
              FlowLocal
            </span>
          </div>
          <p className="font-sans text-md font-semibold text-text">
            {t("Диктовка, которая работает без интернета.")}
          </p>
        </div>
        {/* Четыре строки обещания уехали под «подробнее»: витрина должна
            читаться за секунду, а доказательство нужно тому, кто в обещание не
            поверил. Отрицательная гарантия сильнее обещания: не «мы защищаем
            данные», а «уходить им некуда». */}
        <SettingRow
          icon={<Icon name="shield" size={20} />}
          subtitle={t("Голос не покидает этот компьютер - ему некуда уходить")}
          more={
            t("Интернет нужен один раз, чтобы скачать модель, и ещё ") +
            t("чтобы проверять обновления. Поэтому диктовка работает ") +
            t("в поезде, на даче и когда интернет упал.")
          }
        />
      </Card>

      <Heading>{t("Что важно знать")}</Heading>
      <Card>
        <SettingRow
          first
          icon={<Icon name="history" size={20} />}
          title={t("Первые слова не теряются")}
          subtitle={t("Микрофон слушает чуть раньше, чем вы нажали клавишу")}
        />
        <SettingRow
          icon={<Icon name="shield" size={20} />}
          title={t("Ничего не переписывает")}
          subtitle={t("Вычёркивает лишнее, но не дописывает")}
          more={
            t("Ни одно слово в тексте не появится само - только ") +
            t("исчезнет то, что вы сказали между делом")
          }
        />
        <SettingRow
          icon={<Icon name="moon" size={20} />}
          title={t("Не мешает компьютеру")}
          subtitle={t("В покое не тратит ни процессор, ни сеть")}
        />
      </Card>

      {/* Копия личного. Словарь и замены копятся годами, живут в одном файле
          рядом с программой и не воспроизводятся ничем: снёс Windows - и нет
          их. */}
      <Heading>{t("Свои слова и настройки")}</Heading>
      <Card>
        <SettingRow
          first
          icon={<Icon name="download" size={20} />}
          title={t("Сохранить в файл")}
          subtitle={t("Словарь, подстановки и сочетания - в файл")}
          more={
            t("Пригодится при переустановке и на втором компьютере. ") +
            t("Загрузка добавляет, а не затирает")
          }
        >
          <div className="flex gap-2">
            <Button label={t("Сохранить")} onClick={() => void exportData(false)} />
            <Button
              label={t("Сохранить с историей")}
              onClick={() => void exportData(true)}
            />
          </div>
        </SettingRow>
        <SettingRow
          icon={<Icon name="upload" size={20} />}
          title={t("Загрузить из файла")}
          subtitle={t("Добавит к тому, что есть - ничего не пропадёт")}
        >
          <Button label={t("Загрузить")} onClick={() => void importData()} />
        </SettingRow>
      </Card>

      {/* Записи, которые не удалось распознать. Раздел появляется только когда
          такие есть: у человека, у которого всё хорошо, он не должен даже
          мелькать. */}
      {kept.length > 0 ? (
        <>
          <Heading>{t("Несохранённые записи")}</Heading>
          <Card>
            <SettingRow
              first
              icon={<Icon name="file" size={20} />}
              title={t("Речь цела")}
              subtitle={t("Распознать не вышло, но запись сохранилась")}
              more={
                t("Нажмите «Распознать» - текст попадёт в буфер обмена, ") +
                t("и его можно вставить куда нужно.")
              }
            />
            <ul>
              {kept.map((r) => (
                <li key={r.path}>
                  <SettingRow
                    icon={<Icon name="mic" size={20} />}
                    title={r.name}
                    subtitle={r.note}
                  >
                    <div className="flex gap-2">
                      <Button
                        kind="primary"
                        label={t("Распознать")}
                        onClick={() => void redoRecording(r.path)}
                      />
                      <Button
                        kind="danger"
                        label={t("Удалить")}
                        onClick={() => void dropRecording(r.path)}
                      />
                    </div>
                  </SettingRow>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}

      {/* Как обновлялось. Раньше человек видел номер версии и всё: что в ней
          изменилось и чем она отличается от вчерашней - узнать было неоткуда, а
          обновлятор предлагал обновиться, не говоря ради чего. */}
      {releases.length > 0 ? (
        <>
          <Heading>{t("Как обновлялось")}</Heading>
          <Card>
            <ul>
              {releases.map((r, i) => (
                <li key={r.version}>
                  {/* Пункты выпуска - под «подробнее»: их по пять-десять на
                      версию, и раскрытая история была самой длинной стеной
                      текста во всём окне. Строкой осталось то, ради чего список
                      открывают: номер, дата и одна фраза о выпуске. */}
                  <SettingRow
                    first={i === 0}
                    title={t("Версия ") + r.version}
                    subtitle={r.title}
                    more={
                      r.items.length > 0 ? (
                        // Настоящий список, а не строки через дефис: диктор
                        // говорит «список, пять пунктов», а не читает дефисы.
                        <ul className="list-disc pl-4">
                          {r.items.map((s) => (
                            <li key={s}>{withLead(s)}</li>
                          ))}
                        </ul>
                      ) : undefined
                    }
                  >
                    <span className="flex items-center gap-2">
                      {/* «Сейчас у вас» - единственное, ради чего этот список
                          открывают дважды. */}
                      {r.current ? (
                        <span className="rounded-full bg-fill px-[7px] py-[2px] font-sans text-2xs text-text-secondary">
                          {t("сейчас у вас")}
                        </span>
                      ) : null}
                      <span className="font-mono text-2xs text-text-muted">{r.date}</span>
                    </span>
                  </SettingRow>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}

      {/* Прежние версии (архив 0.x) - выплывающей панелью. В CHANGELOG.md весь
          0.x схлопнут в строку «1.0» намеренно, а полная история лежит в
          docs/history-0.x.md и открывается этой кнопкой. Нет файла (старая
          сборка) - кнопки просто нет. */}
      {old.length > 0 ? (
        <div>
          <Button label={t("Прежние версии")} onClick={() => setShowOld(true)} />
        </div>
      ) : null}
      <VersionsDialog
        open={showOld}
        onClose={() => setShowOld(false)}
        title={t("Прежние версии")}
        versions={old}
      />

      <Heading>{t("Служебное")}</Heading>
      <Card>
        {/* Сводка - под «подробнее» и моноширинным: это данные для письма в
            поддержку, а не настройка. Развёрнутой она занимала шесть строк на
            странице, куда заходят за кнопками под ней. */}
        <SettingRow
          first
          icon={<Icon name="about" size={20} />}
          title={t("Что под капотом")}
          subtitle={t("Версия, модель, микрофон - одним списком")}
          moreMono
          more={<span className="whitespace-pre-wrap">{info}</span>}
        />
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button label={t("Папка приложения")} onClick={() => void openFolder()} />
        {/* Не имена файлов: рядом с «Папка приложения» они читались как список
            того, что лежит внутри, а не как кнопки. Куда они ведут, видно после
            нажатия - открывается тот же файл. */}
        <Button label={t("Файл настроек")} onClick={() => void openConfig()} />
        <Button label={t("Журнал работы")} onClick={() => void openLog()} />
        <Button
          label={t("Пройти знакомство заново")}
          onClick={() => void restartOnboarding()}
        />
      </div>
    </>
  );
}
