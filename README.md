# MLDSL (RU-first)

MLDSL — язык и компилятор для Mineland K+ (Minecraft), который компилирует `.mldsl` в `plan.json` для мода BetterCode (MLBetterCode) и команды `/mldsl run`.

## Документация (RU)

- Быстрый старт: `docs/QUICKSTART_RU.md`
- Полный гайд: `docs/MLDSL_GUIDE_RU.md`

## Что нужно для печати в игре

- Мод BetterCode (MLBetterCode) для Minecraft 1.12.2 Forge: https://github.com/rainbownyashka/mlbettercode
- `plan.json`, сгенерированный компилятором MLDSL

## Установка (Windows)

Рекомендуемый вариант — **установщик** (кладёт `mldsl.exe`, assets, seed-`out/`, опционально ставит VS Code расширение и добавляет контекстное меню).

- Releases: https://github.com/rainbownyashka/mldsl/releases
- Что именно ставится и какие есть опции: `installer/README.md`

## Быстрый запуск

1) Скомпилировать файл в `plan.json`:
- `mldsl compile test.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"`

2) В игре распечатать план:
- `/mldsl run "%APPDATA%\\.minecraft\\plan.json"`

## Разработка (генерация API/доков)

Локальная генерация `out/` требует экспортов из игры:
- `%APPDATA%\\.minecraft\\regallactions_export.txt` (или `MLDSL_REGALLACTIONS_EXPORT=<путь>`)
- (опционально) `apples.txt`

Команда:
- `python tools/build_all.py`

Единый конвейер (проверки + сборка):
- `python tools/pipeline.py fast` (или `dev` / `release`)
- подробности: `packaging/BUILDING.md`

Для CI/релизов используется зафиксированный snapshot `seed/out/` (см. `seed/README.md`).

## Лицензия

См. `LICENSE`.
