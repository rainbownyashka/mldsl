# MLDSL — гайд (RU)

MLDSL компилирует `.mldsl` в `plan.json`, который печатается модом BetterCode (MLBetterCode) через `/mldsl run`.

## Поток работы

1) Пишешь код в `.mldsl`
2) Компилируешь в `plan.json`
3) В игре запускаешь печать: `/mldsl run "<путь_к_plan.json>"`

## События

Базовый синтаксис:

```mldsl
event("Вход игрока") {
    player.message("Привет!")
}
```

Список событий зависит от сервера и сборки API (генерируется из `regallactions_export.txt`).

## Действия

Действия вызываются как функции, обычно в виде `модуль.функция(...)`, например:

```mldsl
player.message("Текст")
player.title("Заголовок", "Подзаголовок", 10, 70, 20)
```

Подсказки/аргументы/enum’ы удобнее смотреть через VS Code расширение **MLDSL Helper**.

## Условия

Условия — это блоки с фигурными скобками:

```mldsl
if_player.имеет_право(право_для_проверки="Белый список") {
    player.message("ОК")
}
```

## Компиляция

### CLI

```powershell
mldsl compile file.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"
```

### Проводник (контекстное меню)

Если включить опцию в установщике, ПКМ по `.mldsl` → “MLDSL: Скомпилировать в plan.json”.

## Генерация API/документации (для разработки)

Локальная пересборка `out/` требует экспортов из игры:
- `%APPDATA%\\.minecraft\\regallactions_export.txt` (или `MLDSL_REGALLACTIONS_EXPORT=<путь>`)
- (опционально) `apples.txt`

Команда:

```powershell
python tools/build_all.py
```

Для релизов используется snapshot `seed/out/` (попадает в установщик).

