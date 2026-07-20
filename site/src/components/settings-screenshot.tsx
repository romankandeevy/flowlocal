import { BlurFade } from "@/components/blur-fade";

export function SettingsScreenshot() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[820px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Выглядит так, как вам удобно
          </h2>
          <p className="mt-2 text-secondary">
            Светлая или тёмная — следом за Windows или по вашему выбору.
            Настройки карточками или строками. Спрашиваем при первом запуске,
            меняется когда угодно.
          </p>
        </BlurFade>

        <BlurFade delay={0.1}>
          <figure className="mt-5">
            <div className="overflow-hidden rounded-[var(--radius-xl)] border border-border">
              <picture>
                <source
                  media="(prefers-color-scheme: dark)"
                  srcSet="/flowlocal/settings_dark.webp"
                />
                <img
                  src="/flowlocal/settings.webp"
                  alt="Шесть страниц настроек: главная, диктовка, слова, история, статистика, о программе"
                  className="block w-full"
                  width={820}
                  height={512}
                  loading="lazy"
                  decoding="async"
                />
              </picture>
            </div>
            <figcaption className="mt-2 text-center text-xs text-muted">
              Шесть страниц. Каталог моделей спрятан вглубь намеренно:
              человеку, который пишет письма, зоопарк моделей видеть незачем.
            </figcaption>
          </figure>
        </BlurFade>
      </div>
    </section>
  );
}
