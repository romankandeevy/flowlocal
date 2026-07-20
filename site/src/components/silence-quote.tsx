import { BlurFade } from "@/components/blur-fade";

export function SilenceQuote() {
  return (
    <section className="px-4 py-14">
      <div className="mx-auto max-w-[620px]">
        <BlurFade>
          <h2 className="text-[26px] font-bold tracking-[-0.02em]">
            Не выдумывает текст в тишине
          </h2>
          <blockquote className="mt-4 border-l-2 border-border-strong pl-5 text-[17px] leading-relaxed text-secondary">
            У Whisper есть фирменная болезнь: на паузах он дописывает «Спасибо
            за просмотр!» и прочее из субтитров, которых наслушался. Лечат это
            отдельным детектором речи. У нас лечить нечего — RNN-T нечем
            выдумывать: у него нет авторегрессивного декодера. Проверено:
            цифровая тишина, шум, гул, щелчок — на выходе пусто.
          </blockquote>
        </BlurFade>
      </div>
    </section>
  );
}
