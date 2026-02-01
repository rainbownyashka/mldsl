# MLDSL — быстрый старт (RU)

## 1) Собрать API (локально)

`python tools/build_all.py`

Это сгенерирует `out/api_aliases.json` и локальные доки в `out/docs/`.

## 2) Скомпилировать файл в plan.json

Вариант “печатать в stdout”:

`python tools/mldsl_compile.py test.mldsl --print-plan`

Вариант “записать план” (по умолчанию в `%APPDATA%\\.minecraft\\plan.json`):

`python tools/mldsl_compile.py test.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"`

## 3) Запуск в игре

`/mldsl run "%APPDATA%\\.minecraft\\plan.json"`

Важно: для “печати” нужен мод BetterCode (MLBetterCode):
- https://github.com/rainbownyashka/mlbettercode

## 4) Минимальные примеры

### Событие

```mldsl
event("Вход игрока") {
    player.message("Привет!")
}
```

### Выборка

```mldsl
select.allplayers {
    player.message("hi")
}
```

### Выдать предметы (через item(...))

```mldsl
игрок.выдать_предметы(
    item("stone", count=3),
    item("diamond", count=2)
)
```
