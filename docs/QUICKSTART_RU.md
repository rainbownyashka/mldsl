# MLDSL — быстрый старт (RU)

## 1) Сборка API/доков

`python tools/build_all.py`

## 2) Компиляция файла

`python tools/mldsl_compile.py test.mldsl`

Полезно для отладки (посмотреть plan.json):

`python tools/mldsl_compile.py test.mldsl --print-plan`

## 3) Минимальный пример

```mldsl
событие(вход) {
    player.message("Привет!")
}
```

## 4) Функции

```mldsl
func hello {
    player.message("Hello")
}

событие(вход) {
    hello()
}
```

## 5) Переменные и присваивание

```mldsl
event(вход) {
    score = 1
    save total = 10
    %selected%counter = %selected%counter + 1
}
```

## 6) Условия

```mldsl
событие(вход) {
    if %selected%counter < 2 {
        player.message("Мало")
    }
    если_игрок.сообщение_равно("!ping") {
        player.message("pong")
    }
}
```

## 7) Импорт модулей (других файлов)

```mldsl
использовать продвинутые_массивы
использовать ext/продвинутые_массивы
import extarray from ext
```

## Где смотреть список функций

- Индекс: `out/docs/README.md`
- Полный список: `out/docs/ALL_FUNCTIONS.md`
