# Опись настроек: что на каждой странице

Снимается разбором `qml/windows/Settings.qml`, а не глазами:
`python tools/settings_inventory.py --md`. Поменялась вёрстка -
перегенерировать, иначе опись врёт.

Зачем. Фаза 4 переносит страницы по одной, и критерий там жёсткий:
после прохода `config.json` совпадает с тем, что даёт QML-версия.
Сверять надо по списку, а не по памяти - пропущенная настройка тихо
исчезает у людей на руках.

| Страница | Строки | Ключей | Вызовов |
|---|---|---|---|
| `Главная` | 449-1050 (602) | 1 | 10 |
| `История` | 1053-1225 (173) | 1 | 3 |
| `Статистика` | 1228-1553 (326) | 0 | 4 |
| `Заметки` | 1565-1886 (322) | 0 | 7 |
| `Диктовка` | 1903-2645 (743) | 16 | 11 |
| `Дополнительно` | 2654-3044 (391) | 10 | 7 |
| `Слова` | 3049-3397 (349) | 0 | 7 |
| `О программе` | 3400-3655 (256) | 0 | 11 |

## Чего критерий из плана не ловит

Настроек с ключом - 28, а действий без ключа - 55.
Критерий фазы 4 («`config.json` после прохода совпадает с QML-версией»)
проверяет только первые 28 из 83: у остальных
ключа нет вовсе, и в конфиге их пропажа не видна никак.

Четыре страницы из восьми - `Статистика`, `Заметки`, `Слова`,
`О программе` - не пишут в конфиг ни одного ключа. Для них этот
критерий не значит ровно ничего: страницу можно перенести пустой и
сверка пройдёт.

Значит, на каждую страницу нужен второй критерий - список вызовов ниже
пройден руками, каждый делает то же, что в QML-версии. Кнопка, которая
молчит, - это не «мелочь на потом»: у человека она просто перестала
работать, и узнает он об этом раньше нас.

## `Главная`

Строки 449-1050 в `Settings.qml`.

**Ключи конфига.** Каждый должен читаться и писаться после переноса.

- `hotkey_hold`

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.acceptSuggestion()`
- `B.ago()`
- `B.copyText()`
- `B.declineSuggestion()`
- `B.homeData()`
- `B.llmBusy()`
- `B.llmInstall()`
- `B.llmState()`
- `B.statusInfo()`
- `B.suggestions()`

## `История`

Строки 1053-1225 в `Settings.qml`.

**Ключи конфига.** Каждый должен читаться и писаться после переноса.

- `history`

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.clearHistory()`
- `B.copyText()`
- `B.historyData()`

## `Статистика`

Строки 1228-1553 в `Settings.qml`.

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.addToDictionary()`
- `B.calendar()`
- `B.insights()`
- `B.stats()`

## `Заметки`

Строки 1565-1886 в `Settings.qml`.

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.copyText()`
- `B.deleteNote()`
- `B.newNote()`
- `B.noteText()`
- `B.notesList()`
- `B.saveNote()`
- `B.tidyNote()`

## `Диктовка`

Строки 1903-2645 в `Settings.qml`.

**Ключи конфига.** Каждый должен читаться и писаться после переноса.

- `cleanup`
- `inbox_path`
- `keep_mic_open`
- `llm.enabled`
- `llm.model`
- `llm.url`
- `mic_device`
- `notes_open`
- `overlay_position`
- `punctuation`
- `smart_join`
- `stream_asr`
- `tech_terms`
- `theme`
- `ui_language`
- `voice_commands`

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.addAutoEnterApp()`
- `B.llmBusy()`
- `B.llmInstall()`
- `B.llmState()`
- `B.pickInboxPath()`
- `B.punctBusy()`
- `B.punctModelInstall()`
- `B.punctModelReady()`
- `B.removeAutoEnterApp()`
- `B.runningApps()`
- `B.setTechTerms()`

## `Дополнительно`

Строки 2654-3044 в `Settings.qml`.

**Ключи конфига.** Каждый должен читаться и писаться после переноса.

- `append_space`
- `device`
- `english_speech`
- `insert_mode`
- `layout`
- `min_record_sec`
- `model`
- `pre_buffer_sec`
- `restore_clipboard`
- `sounds`

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.deleteModel()`
- `B.dmlRun()`
- `B.dmlState()`
- `B.downloadModel()`
- `B.modelsInfo()`
- `B.setModel()`
- `B.setRestart()`

## `Слова`

Строки 3049-3397 в `Settings.qml`.

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.clearDeclined()`
- `B.setDictionary()`
- `B.setSnippetPreset()`
- `B.setSnippetPresetValue()`
- `B.setTransformShown()`
- `B.snippetPresets()`
- `B.transformPresets()`

## `О программе`

Строки 3400-3655 в `Settings.qml`.

**Вызовы `Backend`.** Ключа у них нет, по `config.json` их пропажу не видно.

- `B.about()`
- `B.changelog()`
- `B.dropRecording()`
- `B.exportData()`
- `B.importData()`
- `B.openConfig()`
- `B.openFolder()`
- `B.openLog()`
- `B.redoRecording()`
- `B.restartOnboarding()`
- `B.savedRecordings()`
