# MLDSL (RU-first)

MLDSL — язык/компилятор для Mineland‑кодинга (Minecraft). Он компилирует `.mldsl` в `plan.json`, который исполняется модом BetterCode командой `/mldsl run`.

## Документация

- Быстрый старт (RU): `docs/QUICKSTART_RU.md`
- Полный гайд (RU): `docs/MLDSL_GUIDE_RU.md`

## Требуется мод в игре

Исполнение `plan.json` в Minecraft делает мод BetterCode (MLBetterCode):

- https://github.com/rainbownyashka/mlbettercode

## Установка (Windows)

Скачай установщик из Releases и запусти. Установщик:

- ставит `mldsl.exe` и нужные ассеты;
- кладёт seed‑`out/` в `%LOCALAPPDATA%\\MLDSL\\out`, чтобы всё работало сразу;
- опционально ставит VS Code расширение `MLDSL Helper`.

### Опции установщика

- **Добавить в PATH** — можно вызывать `mldsl` из любой папки.
- **Контекстное меню проводника** — добавляет пункт для `.mldsl`:
  - “MLDSL: Скомпилировать в plan.json” → компилирует выбранный файл в `%APPDATA%\\.minecraft\\plan.json`.
- **Установить расширение VS Code** — если VS Code найден, установщик попытается поставить `.vsix` автоматически.

Если VS Code не установлен — подсказки/hover/autocomplete работать не будут, но компиляция через `mldsl.exe` всё равно доступна.

## Быстрые команды

- Компиляция в `plan.json` (пример):
  - `mldsl compile test.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"`
- Запуск в игре:
  - `/mldsl run "%APPDATA%\\.minecraft\\plan.json"`

## Разработка / пересборка API

Сгенерировать `out/` из локальных экспортов:

- `python tools/build_all.py`

В CI/релизах используется снапшот `seed/out/` (см. `seed/README.md`).

## Лицензия

См. `LICENSE`.

