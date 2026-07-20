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
Keyboard, Qt Lottie. В FlowLocal их нет: осциллограмма нарисована средствами
Qt Quick (LGPLv3), анимации — штатными NumberAnimation/Behavior, а графики
статистики с 20.07.2026 рисует страница на React обычными div и SVG.

Qt WebView — тоже LGPLv3, и с 20.07.2026 он в сборке есть
-----------------------------------------------------------

Окно настроек переехало на страницу, которую показывает Qt WebView:
Qt6WebView.dll, Qt6WebViewQuick.dll, Qt6WebSockets.dll и плагин
plugins/webview/qtwebview_webview2.dll — вместе около 0.4 МБ. Условия те же,
что у остального Qt: динамическая линковка, onedir, библиотеки заменяемы.

Самого движка в сборке НЕТ. Страницу рисует WebView2 Runtime — компонент
Microsoft, часть Windows 11; на Windows 10 приезжает через Windows Update.
Мы его не раздаём и не линкуем, поэтому его лицензия к нашей раздаче
отношения не имеет.

Qt WebEngine (это другой модуль, со встроенным Chromium) в сборку НЕ
включается — он весит 208.6 МБ и здесь не нужен.

Библиотеки страницы настроек (web/dist)
---------------------------------------

Собранная страница едет в сборке файлом web/dist/assets/index-*.js, и внутри
него - чужой код. Все библиотеки под MIT, то есть требуют сохранения
уведомления об авторстве:

  * React и React DOM — https://github.com/facebook/react
  * Radix UI (accordion, dialog, select, slider, switch, tabs, tooltip)
    — https://github.com/radix-ui/primitives
  * zustand — https://github.com/pmndrs/zustand
  * Tailwind CSS (только на сборке, в результат не попадает)
    — https://github.com/tailwindlabs/tailwindcss

Точные версии - в web/package-lock.json, он лежит в репозитории.

Где именно лежит уведомление, проверено, а не предположено. React вставляет
в свой код блок /** @license React ... */, и сборщик его сохраняет - в
собранном файле таких блоков пять. Radix и zustand таких блоков не ставят
вовсе, поэтому уведомление о них - вот этот перечень. Он едет в папке
licenses/ вместе с программой, чего MIT и требует.

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
