# MLDSL Helper (VS Code)

Расширение даёт автодополнение/подсказки для `.mldsl` на базе сгенерированных файлов `out/api_aliases.json` и `out/docs/`.

## Что умеет

- Автодополнение `player.*`, `if_player.*`, `game.*`, …
- Подсказки аргументов внутри `(...)`:
  - ключи параметров (включая RU алиасы вида `режим_игры=` для `rezhim_igry=`)
  - значения enum’ов (список вариантов)
- Hover: показывает описание действия (с цветами `§`)
- F12 (Go to Definition): открывает markdown-док действия из `out/docs/...`
- Команды:
  - `MLDSL: Compile & Copy Command(s)` — компилирует и копирует команды
  - `MLDSL: Compile to plan.json` — пишет `plan.json` (по умолчанию в `%APPDATA%\.minecraft\plan.json`)
  - `MLDSL: Publish Module (open Hub + files)` — собирает временный набор файлов + `plan.json`, открывает Hub и папку

## Установка

Самый простой способ — **через установщик MLDSL** (он кладёт `out/` в `%LOCALAPPDATA%\MLDSL\out` и может поставить VSIX).

Ручная установка VSIX:

1) `Ctrl+Shift+P` → `Extensions: Install from VSIX...`
2) выбрать `mldsl-helper.vsix`

## Настройки

- `mldsl.apiAliasesPath` — путь к `api_aliases.json` (можно пусто: авто-поиск)
- `mldsl.docsRoot` — путь к `out/docs` (можно пусто: авто-поиск)
- `mldsl.compilerPath` — путь к `mldsl.exe` (рекомендуется) или `tools/mldsl_compile.py` (legacy)
- `mldsl.planPath` — куда писать `plan.json` (по умолчанию `%APPDATA%\.minecraft\plan.json`)

## Публикация расширения (автообновления)

VS Code автообновляет расширения только если они опубликованы в Marketplace/OpenVSX.
Это *не обязательно* (установщик MLDSL может ставить VSIX оффлайн), но можно сделать дополнительно.

См. `packaging/BUILDING.md` раздел “Публикация расширения”.

