# MLDSL (RU-first)

MLDSL — язык и компилятор для Mineland K+ (Minecraft), который компилирует `.mldsl` в `plan.json` для мода BetterCode (MLBetterCode) и команды `/mldsl run`.

## SoT документация

- Runbook: `docs/AGENT_RUNBOOK.md`
- Status: `docs/STATUS.md`
- Backlog: `docs/TODO.md`
- Cross-project map: `docs/CROSS_PROJECT_INDEX.md`

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

## `vfunc` (MVP)

Поддержаны виртуальные функции (compile-time expansion):

```mldsl
vfunc basicselectvar(varname, mobid="universeV1")
    select.allentities
    select.if_player.переменная_существует(var=varname)
    player.msg(text=mobid)

event("Вход") {
    basicselectvar(%selected%apiversion)
}
```

- `vfunc` разворачивается на этапе компиляции в обычные строки MLDSL.
- `vfunc` только top-level.
- рекурсия/циклы между `vfunc` запрещены (fail-fast).

## `multiselect` (MVP)

Поддержан compile-time sugar для взвешенной выборки:

```mldsl
event("Вход") {
    multiselect ifplayer %selected%sel 1
        select.ifplayer.держит(item=item("minecraft:stick"))+
        select.ifplayer.переменная_существует(var=%selected%apiversion)-2
        select.ifplayer.переменная_существует(var=%selected%specvar)*=%selected%specvar
}
```

- Блок разворачивается на этапе компиляции в обычные `select.*` и `var.set_*` действия.
- Поддержаны веса:
  - коротко: `+`, `-2`, `*3`, `/2`
  - полно: `+=x`, `-=x`, `*=x`, `/=x`
- В конце автоматически добавляется пороговая проверка:
  - `select.ifplayer|ifmob|ifentity.сравнить_число_легко(counter, threshold, тип_проверки="≥ (Больше или равно)")`

## Разработка (генерация API/доков)

Локальная генерация `out/` требует экспортов из игры:
- `%APPDATA%\\.minecraft\\regallactions_export.txt` (или `MLDSL_REGALLACTIONS_EXPORT=<путь>`)
- (опционально) `apples.txt`

Команда (инкрементальная, с `SKIP/RUN`):
- `python tools/build_all.py`
- принудительно всё пересобрать: `python tools/build_all.py --force`

Единый конвейер (проверки + сборка):
- `python tools/pipeline.py fast` (или `dev` / `release`)
- подробности: `packaging/BUILDING.md`

Для CI/релизов используется зафиксированный snapshot `seed/out/` (см. `seed/README.md`).

## Лицензия

См. `LICENSE`.
