# Установщик MLDSL (Windows)

Установщик ставит MLDSL как обычную программу и помогает сразу получить автоподсказки/компиляцию.

## Что устанавливается

- `mldsl.exe` в `{Program Files}\\MLDSL`
- read-only assets в `{Program Files}\\MLDSL\\assets\\`:
  - `Aliases.json`, `LangTokens.json`, `allactions.txt`
- seed-версия `out/` в `%LOCALAPPDATA%\\MLDSL\\out` (доки + `api_aliases.json`), чтобы **не нужен был Python** и экспорты из игры

## Опции установщика

- Установить MLDSL (компилятор, docs, расширение) — **включено по умолчанию**
  - Если выключить, установщик может работать как “обновление BetterCode без установки MLDSL”.
- Добавить `mldsl` в `PATH` (можно запускать `mldsl` из любой папки) — по умолчанию **выключено**
- Добавить пункт в контекстное меню Проводника для `.mldsl`:
  - “MLDSL: Скомпилировать в plan.json” → пишет в `%APPDATA%\\.minecraft\\plan.json`
  - по умолчанию **выключено**
- Установить расширение VS Code `MLDSL Helper` (если VS Code найден)
  - Если VS Code не найден — установщик покажет инструкцию “Install from VSIX”.
  - Скачать VS Code: https://code.visualstudio.com/
- Скачать/обновить мод BetterCode в `%APPDATA%\\.minecraft\\mods`
  - Берётся последний релиз из `https://github.com/rainbownyashka/mlbettercode/releases`
  - Нужен интернет во время установки

## Где хранится генерируемое

Все данные (логи/кэши/доки) лежат в `%LOCALAPPDATA%\\MLDSL\\...`.

Portable-режим:
- `MLDSL_PORTABLE=1` или файл `portable.flag` рядом с `mldsl.exe`
- тогда данные идут в `<папка_с_exe>\\MLDSL\\...`
