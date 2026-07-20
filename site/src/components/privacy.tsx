import { BlurFade } from "@/components/blur-fade";
import { GlobeLock, FileText, Eye } from "lucide-react";

const items = [
  {
    title: "Некуда отправлять",
    description:
      "В программе нет ни аккаунта, ни сервера, ни адреса, куда слать. Интернет нужен дважды: скачать модель и проверить обновления.",
    icon: GlobeLock,
  },
  {
    title: "История у вас",
    description:
      "Лежит файлом рядом с программой. Можно выключить совсем, можно забывать через месяц, можно выгрузить и унести.",
    icon: FileText,
  },
  {
    title: "Открытый код",
    description:
      "Лицензия MIT. Не верите на слово — читайте, собирайте сами.",
    icon: Eye,
  },
];

export function Privacy() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[620px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Приватность, которую нечем нарушить
          </h2>
          <p className="mt-2 text-secondary">
            Это не обещание в политике конфиденциальности, а устройство
            программы.
          </p>
        </BlurFade>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {items.map((item, i) => (
            <BlurFade key={item.title} delay={i * 0.1}>
              <div className="flex h-full flex-col rounded-[var(--radius-lg)] border border-border bg-paper p-5">
                <item.icon className="mb-3 size-5 text-accent" />
                <h3 className="text-sm font-medium">{item.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {item.description}
                </p>
              </div>
            </BlurFade>
          ))}
        </div>
      </div>
    </section>
  );
}
