FlowLocal — лицензии сторонних компонентов
==========================================

Сам FlowLocal — MIT, текст в LICENSE рядом с этим файлом.

LGPLv3 — требует внимания
-------------------------

PySide6 (Qt) распространяется под LGPLv3. FlowLocal линкуется с ним
динамически (обычный `import PySide6`) и раздаётся папкой, а не одним
запечатанным .exe — именно поэтому сборка onedir:

  * §4(a) — уведомление и текст лицензии: этот файл, Qt-LGPLv3.txt и
            GPLv3.txt рядом (LGPL включает в себя условия GPL по ссылке,
            поэтому оба текста);
  * §4(d) — возможность перелинковать приложение со своей сборкой Qt:
            библиотеки Qt лежат отдельными файлами в папке приложения,
            их можно заменить своими;
  * §4(e) — исходники Qt: https://download.qt.io/official_releases/qt/
            Информация о лицензии: https://www.qt.io/licensing/open-source-lgpl-obligations

Модули Qt, которые НЕЛЬЗЯ подключать (они GPL-only и утянут проект в GPL):
Qt Graphs, Qt Quick 3D, Qt Quick Timeline, Qt Qml Compiler, Qt Virtual
Keyboard, Qt Lottie. В FlowLocal их нет: осциллограмма и график статистики
нарисованы средствами Qt Quick (LGPLv3), анимации — штатными
NumberAnimation/Behavior.

Остальные зависимости
---------------------

  onnx-asr, onnxruntime, keyboard, sounddevice, pynput  — MIT
  Pillow                                                — MIT-CMU
  numpy                                                 — BSD-3-Clause
  huggingface_hub                                       — Apache-2.0
  pywin32                                               — PSF

Шрифты
------

Onest и JetBrains Mono — SIL Open Font License 1.1. Тексты лицензий лежат
рядом со шрифтами: assets/fonts/OFL-*.txt.

Модели
------

В сборку не входят — качаются при первом запуске в models/ рядом с
приложением:

  GigaAM v3 (SberDevices)  — MIT
  Whisper (OpenAI)         — MIT
  Parakeet (NVIDIA)        — CC-BY-4.0: требует указания авторства,
                             если вы её включите
