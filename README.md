# MLDSL (RU-first)

MLDSL — DSL/компилятор для Mineland-кодинга (Minecraft), который превращает `.mldsl` в `plan.json` для исполнения модом через `/mldsl run`.

## Документация

- Быстрый старт (RU): `docs/QUICKSTART_RU.md`
- Полный гайд (RU): `docs/MLDSL_GUIDE_RU.md`

## Печать в игре (нужен мод)

Для исполнения `plan.json` в игре нужен клиентский мод BetterCode (MLBetterCode):
- https://github.com/rainbownyashka/mlbettercode

## Сборка каталога действий (локально)

Каталог действий и автодоки генерируются локально в `out/`:

- `python tools/build_all.py`

Папка `out/` не коммитится в Git (перегенерируется на машине).

## VSCode

- Расширение: `tools/mldsl-vscode/`
- Готовый `.vsix` (локальная сборка): `tools/mldsl-vscode/mldsl-helper-0.0.20.vsix`

## Лицензия

Некоммерческая (продажа/коммерческое использование запрещены без разрешения) — см. `LICENSE`.
