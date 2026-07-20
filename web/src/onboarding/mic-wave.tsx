// Живая волна микрофона в мастере: холст Canvas 2D, тридцать кадров в секунду.
//
// **Почему не WaveMeter из ui/chart.** Тот рисует сорок <div> и меняет им
// высоту стилями. На витрине это честно - там волна стоит. Здесь она живая, и
// тридцать раз в секунду сорок изменений раскладки - это сорок пересчётов
// стиля на кадр. На холсте кадр стоит одну заливку. Считалки уровня и пик-метра
// взяты оттуда же, а не написаны заново: разъедутся - и волна на двух экранах
// будет разной высоты от одного и того же голоса.
//
// **Почему тридцать, а не шестьдесят.** Это не пилюля. У пилюли данные не
// ходят через мост и фокус ей брать нельзя, поэтому там честные шестьдесят на
// render-потоке (разбор в шапке overlay_qt.py). Здесь каждый кадр - запрос по
// сокету, а окно мастера человек держит прямо перед собой. Тридцати хватает,
// чтобы волна отвечала голосу, и план говорит ровно это.
//
// **Уровни настоящие.** levels() тянет их из recorder приложения, а не из
// муляжа: мастер, который показывает нарисованную волну, проверяет сам себя, и
// «микрофон не тот» человек узнал бы уже после мастера.
//
// drain_levels отдаёт замеры ОДИН раз, а тянут их двое - экран микрофона и
// экран пробы. Тянущие разом обкрадывали бы друг друга, поэтому опрос заводит
// только тот экран, который сейчас виден: это и есть `running`.
import { useEffect, useRef } from "react";

import { levels } from "../bridge/api";
import { decayPeak, levelFromRms } from "../ui/chart/wave-meter";
import { cn } from "../ui/cn";

/** 33 мс - те самые тридцать кадров. Столько же стояло в QML-версии. */
const TICK_MS = 33;

/** Порог, за которым страница говорит «слышу вас». Из QML, не подобран заново. */
const HEARD_AT = 0.45;

export interface MicWaveProps {
  /** Опрашивать микрофон. false - волна ложится и замеры не копятся. */
  running: boolean;
  bars?: number;
  barWidth?: number;
  gap?: number;
  maxHeight?: number;
  /**
   * Слышно ли голос прямо сейчас. Зовётся только когда ответ меняется, а не
   * каждый кадр: значение идёт в одну строку из двух слов, и перерисовывать
   * ради неё экран тридцать раз в секунду незачем.
   */
  onHeard?: (heard: boolean) => void;
  className?: string;
}

export function MicWave({
  running,
  bars = 40,
  barWidth = 5,
  gap = 3,
  maxHeight = 96,
  onHeard,
  className,
}: MicWaveProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const bufRef = useRef<number[]>([]);
  const peakRef = useRef(0);
  const heardRef = useRef(false);
  // Обработчик через ref: он приходит новым замыканием на каждую перерисовку
  // родителя, и держи мы его в зависимостях - таймер пересоздавался бы вместе
  // с ним, а волна вставала бы на каждый чужой кадр.
  const heardCb = useRef(onHeard);
  heardCb.current = onHeard;

  const width = bars * barWidth + (bars - 1) * gap;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    // В jsdom холста нет вовсе, и падать из-за этого нельзя: тесты про роли и
    // подписи, а не про пиксели. В WebView2 контекст родной.
    if (!ctx) return;

    // Физических точек больше логических на мониторах с масштабом, и без этого
    // волна выглядит размытой ровно там, где её и разглядывают.
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(maxHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const draw = () => {
      ctx.clearRect(0, 0, width, maxHeight);
      // Краска - у самого холста, через класс text-ink. Своего цвета здесь не
      // заводим: чернила приезжают токеном, и смена темы подхватывается сама,
      // потому что цвет перечитывается на каждом кадре.
      ctx.fillStyle = getComputedStyle(canvas).color;
      ctx.globalAlpha = 0.85;
      const buf = bufRef.current;
      for (let i = 0; i < bars; i++) {
        // Свежий замер - справа: волна едет влево, как осциллограф. Замеров
        // меньше, чем столбиков, - слева честно лежит ровная линия.
        const v = buf[buf.length - bars + i] ?? 0;
        // Тишина - ниточка в три пикселя, а не пустота: иначе непонятно,
        // включён ли микрофон вообще.
        const h = Math.max(3, v * maxHeight);
        const x = i * (barWidth + gap);
        const y = (maxHeight - h) / 2;
        ctx.beginPath();
        // Столбик - пилюля, радиус от ширины, как и в QML. Числом писать
        // нельзя: поменяется ширина - радиус молча станет неправдой.
        ctx.roundRect(x, y, barWidth, h, barWidth / 2);
        ctx.fill();
      }
    };

    const say = (heard: boolean) => {
      if (heard === heardRef.current) return;
      heardRef.current = heard;
      heardCb.current?.(heard);
    };

    if (!running) {
      // Ушли с экрана - забываем накопленное. Иначе, вернувшись, человек
      // увидел бы волну от того, что говорил пять минут назад.
      bufRef.current = [];
      peakRef.current = 0;
      say(false);
      draw();
      return;
    }

    draw();

    let busy = false;
    const id = window.setInterval(() => {
      // Ответ на прошлый запрос ещё не пришёл - второй только удлинит очередь.
      // Волна от этого не отстанет: levels() копит замеры, и следующий ответ
      // принесёт их все разом.
      if (busy) return;
      busy = true;
      void levels().then(
        (fresh) => {
          busy = false;
          if (!Array.isArray(fresh) || fresh.length === 0) return;
          const buf = bufRef.current.slice();
          let last = 0;
          for (const raw of fresh) {
            last = levelFromRms(Number(raw) || 0);
            buf.push(last);
          }
          bufRef.current = buf.slice(-bars);
          peakRef.current = decayPeak(peakRef.current, last);
          say(peakRef.current > HEARD_AT);
          draw();
        },
        () => {
          // Мост не ответил - молчим и пробуем на следующем такте. Ронять из-за
          // этого мастер нельзя: человек пришёл настроить диктовку.
          busy = false;
        },
      );
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, [running, bars, barWidth, gap, maxHeight, width]);

  return (
    // Волна - картинка звука, и рядом с ней экран ставит слово («слышу вас»).
    // Диктору читают слово, а сорока столбикам сказать ему нечего.
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ width, height: maxHeight }}
      className={cn("text-ink", className)}
    />
  );
}
