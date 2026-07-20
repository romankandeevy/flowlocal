# Опись контролов: что переносить и в каком порядке

Снимается разбором: `python tools/controls_inventory.py --md`.
Поменялись контролы - перегенерировать.

Всего 36 контролов, 3969 строк,
322 постановок во всей вёрстке.

**Порядок переноса читается из колонки «ставят».** Контрол, который
стоит в полусотне мест, держит на себе вид всего окна; одиночка не
держит ничего. Начинать с редкого - значит переписывать его второй раз
после того, как выяснится, каким должен быть частый.

| Контрол | Строк | Ставят | Основа |
|---|---|---|---|
| `SettingRow` | 248 | 54 | `Item` |
| `Card` | 74 | 48 | `Item` |
| `FlowButton` | 105 | 44 | `Item` |
| `SectionTitle` | 12 | 23 | `Text` |
| `Icon` | 42 | 17 | `Canvas` |
| `FlowInput` | 76 | 12 | `Item` |
| `Segmented` | 158 | 12 | `Item` |
| `StatRow` | 24 | 11 | `SettingRow` |
| `FocusRing` | 57 | 10 | `Rectangle` |
| `HotkeyField` | 27 | 10 | `HotkeyBox` |
| `PageTitle` | 29 | 10 | `Text` |
| `ToggleRow` | 16 | 10 | `SettingRow` |
| `Icons` | 282 | 9 | `QtObject` |
| `EmptyState` | 119 | 6 | `Item` |
| `Metric` | 204 | 5 | `Card` |
| `Toggle` | 94 | 5 | `Item` |
| `KeyCaps` | 110 | 4 | `Flow` |
| `Note` | 12 | 4 | `Text` |
| `SectionHeader` | 32 | 4 | `Item` |
| `Select` | 172 | 3 | `Item` |
| `Wordmark` | 60 | 3 | `Row` |
| `PairRow` | 51 | 2 | `Row` |
| `Slider` | 120 | 2 | `Item` |
| `WaveMeter` | 93 | 2 | `Item` |
| `Backdrop` | 89 | 1 | `Item` |
| `BarChart` | 256 | 1 | `Item` |
| `CardShadow` | 47 | 1 | `MultiEffect` |
| `HotkeyBox` | 124 | 1 | `Item` |
| `NavItem` | 77 | 1 | `Item` |
| `PairTable` | 296 | 1 | `Card` |
| `PillShadow` | 30 | 1 | `MultiEffect` |
| `SpeedBars` | 120 | 1 | `Card` |
| `StreakCalendar` | 241 | 1 | `Item` |
| `StreakRing` | 231 | 1 | `Card` |
| `TransformTable` | 105 | 1 | `Card` |
| `VersionsDialog` | 136 | 1 | `Item` |

## Интерфейс каждого

Свойства - это будущие props, сигналы - обработчики. Переписывать
интерфейс по дороге не надо: он уже прошёл через живое окно.

### `SettingRow`

248 строк, ставят 54 раз, основа `Item`.

- свойства: `control`, `expanded`, `first`, `icon`, `more`, `moreFont`, `moreFormat`, `mouseFocus`, `pad`, `subtitle`, `textLeft`, `title`
- где: Onboarding.qml, Settings.qml, StatRow.qml, ToggleRow.qml, VersionsDialog.qml

### `Card`

74 строк, ставят 48 раз, основа `Item`.

- свойства: `content`, `lines`, `shadow`
- где: Metric.qml, Onboarding.qml, PairTable.qml, Settings.qml, SpeedBars.qml, StreakRing.qml и ещё

### `FlowButton`

105 строк, ставят 44 раз, основа `Item`.

- свойства: `kind`, `label`, `mouseFocus`, `visualFocus`
- сигналы: `clicked`
- где: EmptyState.qml, Onboarding.qml, PairRow.qml, SectionHeader.qml, Settings.qml, Transcript.qml и ещё

### `SectionTitle`

12 строк, ставят 23 раз, основа `Text`.

- где: SectionHeader.qml, Settings.qml, VersionsDialog.qml

### `Icon`

42 строк, ставят 17 раз, основа `Canvas`.

- свойства: `color`, `path`, `size`, `weight`
- где: EmptyState.qml, Metric.qml, NavItem.qml, Onboarding.qml, PairTable.qml, Picker.qml и ещё

### `FlowInput`

76 строк, ставят 12 раз, основа `Item`.

- свойства: `mono`, `placeholder`, `text`
- сигналы: `edited`
- где: Onboarding.qml, PairRow.qml, Settings.qml, TransformTable.qml

### `Segmented`

158 строк, ставят 12 раз, основа `Item`.

- свойства: `inset`, `mouseFocus`, `options`, `value`, `visualFocus`
- сигналы: `picked`
- функции: `indexOf`, `step`
- где: Onboarding.qml, Settings.qml

### `StatRow`

24 строк, ставят 11 раз, основа `SettingRow`.

- свойства: `value`
- где: Settings.qml

### `FocusRing`

57 строк, ставят 10 раз, основа `Rectangle`.

- свойства: `gap`, `on`, `target`, `targetRadius`
- где: FlowButton.qml, HotkeyBox.qml, NavItem.qml, PairTable.qml, Segmented.qml, Select.qml и ещё

### `HotkeyField`

27 строк, ставят 10 раз, основа `HotkeyBox`.

- свойства: `field`
- функции: `onCaptureDone`
- где: Onboarding.qml, Settings.qml

### `PageTitle`

29 строк, ставят 10 раз, основа `Text`.

- где: Onboarding.qml, Settings.qml

### `ToggleRow`

16 строк, ставят 10 раз, основа `SettingRow`.

- свойства: `path`, `value`
- где: Settings.qml

### `Icons`

282 строк, ставят 9 раз, основа `QtObject`.

- свойства: `about`, `app`, `asr`, `back`, `box`, `briefcase`, `check`, `chevron`, `clipboard`, `code`, `copy`, `dictionary`, `disk`, `download`, `edit`, `enter`, `extra`, `file`, `gauge`, `history`, `home`, `join`, `keyboard`, `languages`, `link`, `list`, `mail`, `mic`, `moon`, `notes`, `palette`, `pill`, `record`, `scissors`, `send`, `settings`, `shield`, `sliders`, `smile`, `sound`, `space`, `sparkles`, `stats`, `steps`, `surface`, `swap`, `target`, `timer`, `trash`, `type`, `undo`, `upload`, `zap`
- функции: `forPage`, `forTransform`
- где: Onboarding.qml, PairTable.qml, SettingRow.qml, Settings.qml, StreakRing.qml, Transcript.qml и ещё

### `EmptyState`

119 строк, ставят 6 раз, основа `Item`.

- свойства: `actionLabel`, `alarm`, `combo`, `hint`, `icon`, `pad`, `title`
- сигналы: `action`
- где: Settings.qml, TransformTable.qml

### `Metric`

204 строк, ставят 5 раз, основа `Card`.

- свойства: `_display`, `_shown`, `countTo`, `hint`, `icon`, `label`, `order`, `pending`, `suffix`, `value`
- функции: `runCount`
- где: Settings.qml

### `Toggle`

94 строк, ставят 5 раз, основа `Item`.

- свойства: `mouseFocus`, `pos`, `value`, `visualFocus`
- сигналы: `toggled`
- функции: `flip`
- где: Onboarding.qml, Settings.qml, ToggleRow.qml

### `KeyCaps`

110 строк, ставят 4 раз, основа `Flow`.

- свойства: `capH`, `combo`, `down`, `held`, `keySize`, `lit`, `parts`
- где: EmptyState.qml, Onboarding.qml, Settings.qml

### `Note`

12 строк, ставят 4 раз, основа `Text`.

- где: Settings.qml

### `SectionHeader`

32 строк, ставят 4 раз, основа `Item`.

- свойства: `buttonKind`, `buttonLabel`, `text`
- сигналы: `action`
- где: Settings.qml

### `Select`

172 строк, ставят 3 раз, основа `Item`.

- свойства: `hover`, `mouseFocus`, `options`, `value`, `visualFocus`
- сигналы: `picked`
- функции: `indexOf`, `labelOf`
- где: Onboarding.qml, Settings.qml

### `Wordmark`

60 строк, ставят 3 раз, основа `Row`.

- свойства: `box`, `nameSize`
- где: Onboarding.qml, Settings.qml

### `PairRow`

51 строк, ставят 2 раз, основа `Row`.

- свойства: `keyText`, `leftPlaceholder`, `rightPlaceholder`, `valueText`
- сигналы: `keyEdited`, `valueEdited`, `removed`
- где: PairTable.qml

### `Slider`

120 строк, ставят 2 раз, основа `Item`.

- свойства: `from`, `mouseFocus`, `pos`, `stepSize`, `suffix`, `to`, `trackW`, `value`, `visualFocus`
- сигналы: `moved`
- функции: `snap`, `set`, `apply`
- где: Settings.qml

### `WaveMeter`

93 строк, ставят 2 раз, основа `Item`.

- свойства: `_levels`, `barColor`, `barW`, `bars`, `gap`, `maxH`, `peak`, `running`
- где: Onboarding.qml

### `Backdrop`

89 строк, ставят 1 раз, основа `Item`.

- свойства: `base`
- функции: `onChanged`, `onChanged`
- где: Settings.qml

### `BarChart`

256 строк, ставят 1 раз, основа `Item`.

- свойства: `avg`, `barGap`, `barsH`, `colW`, `day`, `days`, `full`, `hovered`, `isRecord`, `k`, `labelH`, `lit`, `maxBarW`, `maxValue`, `tipH`
- где: Settings.qml

### `CardShadow`

47 строк, ставят 1 раз, основа `MultiEffect`.

- где: Card.qml

### `HotkeyBox`

124 строк, ставят 1 раз, основа `Item`.

- свойства: `allowClear`, `capturing`, `keyStart`, `mouseFocus`, `pretty`, `value`, `visualFocus`
- сигналы: `startCapture`, `cancelCapture`, `cleared`
- где: HotkeyField.qml

### `NavItem`

77 строк, ставят 1 раз, основа `Item`.

- свойства: `active`, `icon`, `label`, `mouseFocus`, `visualFocus`
- сигналы: `clicked`
- где: Settings.qml

### `PairTable`

296 строк, ставят 1 раз, основа `Card`.

- свойства: `blanks`, `empty`, `leftPlaceholder`, `mouseFocus`, `readyCount`, `readyHint`, `readyOpen`, `readyTitle`, `rightPlaceholder`, `showBlankRow`, `storeKey`
- функции: `reload`, `add`, `recount`, `commit`
- где: Settings.qml

### `PillShadow`

30 строк, ставят 1 раз, основа `MultiEffect`.

- где: Overlay.qml

### `SpeedBars`

120 строк, ставят 1 раз, основа `Card`.

- свойства: `maxWpm`, `progress`, `ratio`, `rows`, `typingWpm`, `voiceWpm`
- где: Settings.qml

### `StreakCalendar`

241 строк, ставят 1 раз, основа `Item`.

- свойства: `cell`, `cellRadius`, `day`, `days`, `gap`, `gridH`, `gridW`, `hovered`, `labelW`, `legendH`, `months`, `monthsH`, `step`, `tipH`, `weekdays`, `weeks`
- функции: `cellColor`
- где: Settings.qml

### `StreakRing`

231 строк, ставят 1 раз, основа `Card`.

- свойства: `best`, `expandable`, `label`, `mouseFocus`, `open`, `progress`, `record`, `shown`, `target`, `value`
- сигналы: `activated`
- функции: `runArc`, `runNum`
- где: Settings.qml

### `TransformTable`

105 строк, ставят 1 раз, основа `Card`.

- свойства: `blanks`, `full`, `limit`
- функции: `reload`, `add`, `recount`, `commit`
- где: Settings.qml

### `VersionsDialog`

136 строк, ставят 1 раз, основа `Item`.

- свойства: `open`, `title`, `versions`
- сигналы: `closed`
- где: Settings.qml

