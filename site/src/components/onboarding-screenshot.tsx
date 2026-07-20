import { BlurFade } from "@/components/blur-fade";

export function OnboardingScreenshot() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[820px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Восемь экранов — и всё готово
          </h2>
          <p className="mt-2 text-secondary">
            Язык, микрофон с живой волной, сочетание, проверка вставки и проба
            голосом: первый текст вы увидите ещё в мастере, никуда его не
            вставляя.
          </p>
        </BlurFade>

        <BlurFade delay={0.1}>
          <figure className="mt-5">
            <div className="overflow-hidden rounded-[var(--radius-xl)] border border-border">
              <img
                src="/flowlocal/onboarding.webp"
                alt="Экраны мастера первого запуска"
                className="block w-full"
                width={820}
                height={512}
                loading="lazy"
                decoding="async"
              />
            </div>
          </figure>
        </BlurFade>
      </div>
    </section>
  );
}
