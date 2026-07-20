// Клиент моста. СГЕНЕРИРОВАНО из Backend - руками не править.
//
//   python tools/gen_bridge.py           переписать
//   python tools/gen_bridge.py --check   сверить (стоит в CI)
//
// Семьдесят пять методов и десять сигналов переносить руками незачем: тут не
// столько работа, сколько 75 поводов опечататься, а опечатка вылезла бы не при
// сборке, а в работающем окне. Здесь она падает на tsc.
//
// Типы аргументов взяты из metaObject, то есть из того же места, откуда их
// берёт сам мост. QVariant и QVariantMap приезжают как unknown и Record -
// точнее Qt про них не знает, и выдумывать за него не надо.

import { call, get, set, onSignal } from "./client";


/** Ключи конфига - все, что есть в config.DEFAULTS. */
export type SettingKey =
  | "append_space"
  | "asr_threads"
  | "auto_enter_apps"
  | "cleanup"
  | "device"
  | "dictionary"
  | "english_speech"
  | "history"
  | "history_days"
  | "hotkey_clipboard"
  | "hotkey_command"
  | "hotkey_hold"
  | "hotkey_inbox"
  | "hotkey_notes"
  | "hotkey_toggle"
  | "hotkey_transform"
  | "inbox_path"
  | "insert_mode"
  | "join_window_sec"
  | "keep_mic_open"
  | "language"
  | "layout"
  | "llm"
  | "mic_device"
  | "min_record_sec"
  | "model"
  | "notes_open"
  | "onboarded"
  | "overlay_position"
  | "overlay_x"
  | "overlay_y"
  | "pause_music"
  | "pre_buffer_sec"
  | "punctuation"
  | "quantization"
  | "question_by_voice"
  | "remove_fillers"
  | "restore_clipboard"
  | "smart_join"
  | "snippets"
  | "snippets_declined"
  | "sounds"
  | "stream_asr"
  | "stream_min_tail_sec"
  | "tech_terms"
  | "theme"
  | "tone_rules"
  | "transforms"
  | "transforms_hidden"
  | "ui_language"
  | "undo_hotkey"
  | "unload_after_min"
  | "voice_commands"
;

/** Прочитать настройку. */
export function getSetting(key: SettingKey): Promise<unknown> {
  return get(key);
}

/** Записать настройку. Мост подтвердит её всем страницам. */
export function setSetting(key: SettingKey, value: unknown): void {
  set(key, value);
}

// ---------- методы Backend ----------

export function about(): Promise<string> {
  return call("about") as Promise<string>;
}

export function acceptSuggestion(a0: string, a1: string): Promise<void> {
  return call("acceptSuggestion", a0, a1) as Promise<void>;
}

export function addAutoEnterApp(a0: string): Promise<void> {
  return call("addAutoEnterApp", a0) as Promise<void>;
}

export function addToDictionary(a0: string, a1: string): Promise<void> {
  return call("addToDictionary", a0, a1) as Promise<void>;
}

export function ago(a0: string): Promise<string> {
  return call("ago", a0) as Promise<string>;
}

export function applyUpdate(): Promise<void> {
  return call("applyUpdate") as Promise<void>;
}

export function calendar(): Promise<Record<string, unknown>> {
  return call("calendar") as Promise<Record<string, unknown>>;
}

export function cancelCapture(): Promise<void> {
  return call("cancelCapture") as Promise<void>;
}

export function changelog(): Promise<unknown[]> {
  return call("changelog") as Promise<unknown[]>;
}

export function clearDeclined(): Promise<void> {
  return call("clearDeclined") as Promise<void>;
}

export function clearHistory(): Promise<void> {
  return call("clearHistory") as Promise<void>;
}

export function copyText(a0: string): Promise<void> {
  return call("copyText", a0) as Promise<void>;
}

export function customTransforms(): Promise<unknown[]> {
  return call("customTransforms") as Promise<unknown[]>;
}

export function declineSuggestion(a0: string): Promise<void> {
  return call("declineSuggestion", a0) as Promise<void>;
}

export function deleteModel(a0: string): Promise<void> {
  return call("deleteModel", a0) as Promise<void>;
}

export function deleteNote(a0: string): Promise<void> {
  return call("deleteNote", a0) as Promise<void>;
}

export function dmlRun(): Promise<void> {
  return call("dmlRun") as Promise<void>;
}

export function dmlState(): Promise<Record<string, unknown>> {
  return call("dmlState") as Promise<Record<string, unknown>>;
}

export function downloadModel(a0: string): Promise<void> {
  return call("downloadModel", a0) as Promise<void>;
}

export function downloadStarter(a0: string): Promise<void> {
  return call("downloadStarter", a0) as Promise<void>;
}

export function dropFile(a0: unknown): Promise<void> {
  return call("dropFile", a0) as Promise<void>;
}

export function dropRecording(a0: string): Promise<void> {
  return call("dropRecording", a0) as Promise<void>;
}

export function englishReady(): Promise<boolean> {
  return call("englishReady") as Promise<boolean>;
}

export function exportData(a0: boolean): Promise<string> {
  return call("exportData", a0) as Promise<string>;
}

export function history(): Promise<unknown[]> {
  return call("history") as Promise<unknown[]>;
}

export function historyData(): Promise<Record<string, unknown>> {
  return call("historyData") as Promise<Record<string, unknown>>;
}

export function homeData(): Promise<Record<string, unknown>> {
  return call("homeData") as Promise<Record<string, unknown>>;
}

export function importData(): Promise<string> {
  return call("importData") as Promise<string>;
}

export function insights(): Promise<Record<string, unknown>> {
  return call("insights") as Promise<Record<string, unknown>>;
}

export function llmBusy(): Promise<boolean> {
  return call("llmBusy") as Promise<boolean>;
}

export function llmInstall(): Promise<void> {
  return call("llmInstall") as Promise<void>;
}

export function llmReady(): Promise<boolean> {
  return call("llmReady") as Promise<boolean>;
}

export function llmState(): Promise<string> {
  return call("llmState") as Promise<string>;
}

export function modelsInfo(): Promise<unknown[]> {
  return call("modelsInfo") as Promise<unknown[]>;
}

export function newNote(): Promise<string> {
  return call("newNote") as Promise<string>;
}

export function noteText(a0: string): Promise<string> {
  return call("noteText", a0) as Promise<string>;
}

export function notesList(a0: string): Promise<unknown[]> {
  return call("notesList", a0) as Promise<unknown[]>;
}

export function oldVersions(): Promise<unknown[]> {
  return call("oldVersions") as Promise<unknown[]>;
}

export function openConfig(): Promise<void> {
  return call("openConfig") as Promise<void>;
}

export function openFolder(): Promise<void> {
  return call("openFolder") as Promise<void>;
}

export function openLog(): Promise<void> {
  return call("openLog") as Promise<void>;
}

export function pairs(a0: string): Promise<unknown[]> {
  return call("pairs", a0) as Promise<unknown[]>;
}

export function pendingUpdate(): Promise<Record<string, unknown>> {
  return call("pendingUpdate") as Promise<Record<string, unknown>>;
}

export function pickInboxPath(): Promise<string> {
  return call("pickInboxPath") as Promise<string>;
}

export function pretty(a0: string): Promise<string> {
  return call("pretty", a0) as Promise<string>;
}

export function punctBusy(): Promise<boolean> {
  return call("punctBusy") as Promise<boolean>;
}

export function punctModelInstall(): Promise<void> {
  return call("punctModelInstall") as Promise<void>;
}

export function punctModelNote(): Promise<string> {
  return call("punctModelNote") as Promise<string>;
}

export function punctModelReady(): Promise<boolean> {
  return call("punctModelReady") as Promise<boolean>;
}

export function redoRecording(a0: string): Promise<void> {
  return call("redoRecording", a0) as Promise<void>;
}

export function removeAutoEnterApp(a0: string): Promise<void> {
  return call("removeAutoEnterApp", a0) as Promise<void>;
}

export function restartOnboarding(): Promise<void> {
  return call("restartOnboarding") as Promise<void>;
}

export function runningApps(): Promise<unknown[]> {
  return call("runningApps") as Promise<unknown[]>;
}

export function saveNote(a0: string, a1: string): Promise<void> {
  return call("saveNote", a0, a1) as Promise<void>;
}

export function savedRecordings(): Promise<unknown[]> {
  return call("savedRecordings") as Promise<unknown[]>;
}

export function setAutostart(a0: boolean): Promise<void> {
  return call("setAutostart", a0) as Promise<void>;
}

export function setCustomTransforms(a0: unknown[]): Promise<void> {
  return call("setCustomTransforms", a0) as Promise<void>;
}

export function setDictionary(a0: string): Promise<void> {
  return call("setDictionary", a0) as Promise<void>;
}

export function setModel(a0: string): Promise<void> {
  return call("setModel", a0) as Promise<void>;
}

export function setPairs(a0: string, a1: unknown[]): Promise<void> {
  return call("setPairs", a0, a1) as Promise<void>;
}

export function setRestart(a0: string, a1: unknown): Promise<void> {
  return call("setRestart", a0, a1) as Promise<void>;
}

export function setSnippetPreset(a0: string, a1: boolean): Promise<void> {
  return call("setSnippetPreset", a0, a1) as Promise<void>;
}

export function setSnippetPresetValue(a0: string, a1: string): Promise<void> {
  return call("setSnippetPresetValue", a0, a1) as Promise<void>;
}

export function setTechTerms(a0: boolean): Promise<void> {
  return call("setTechTerms", a0) as Promise<void>;
}

export function setTransformShown(a0: string, a1: boolean): Promise<void> {
  return call("setTransformShown", a0, a1) as Promise<void>;
}

export function snippetPresets(): Promise<unknown[]> {
  return call("snippetPresets") as Promise<unknown[]>;
}

export function startCapture(a0: string): Promise<void> {
  return call("startCapture", a0) as Promise<void>;
}

export function starterMb(): Promise<number> {
  return call("starterMb") as Promise<number>;
}

export function stats(): Promise<Record<string, unknown>> {
  return call("stats") as Promise<Record<string, unknown>>;
}

export function statusInfo(): Promise<Record<string, unknown>> {
  return call("statusInfo") as Promise<Record<string, unknown>>;
}

export function suggestions(): Promise<unknown[]> {
  return call("suggestions") as Promise<unknown[]>;
}

export function tidyNote(a0: string, a1: string): Promise<void> {
  return call("tidyNote", a0, a1) as Promise<void>;
}

export function transformPresets(): Promise<unknown[]> {
  return call("transformPresets") as Promise<unknown[]>;
}

// ---------- сигналы Backend ----------

export interface Signals {
  captureDone: [string, string];
  changed: [];
  dmlDone: [boolean, string, Record<string, unknown>];
  dmlStage: [string, number];
  flashed: [string, string];
  llmDone: [boolean];
  llmStage: [string, number, number];
  modelProgress: [string, number];
  modelsChanged: [];
  noteTidied: [string, string, string];
}

/** Подписаться на сигнал. Возвращает функцию отписки. */
export function on<K extends keyof Signals>(
  name: K,
  fn: (...args: Signals[K]) => void,
): () => void {
  return onSignal(name as string, fn as (...a: unknown[]) => void);
}
