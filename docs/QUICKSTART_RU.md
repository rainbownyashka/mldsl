# MLDSL — быстрый старт (RU)

## 0) Что нужно

- **В игре:** мод BetterCode (MLBetterCode), чтобы выполнять `plan.json` через `/mldsl run`:
  - https://github.com/rainbownyashka/mlbettercode
- **На ПК (Windows):** установщик MLDSL из Releases (ставит `mldsl.exe`).
- **Для удобства:** VS Code (опционально) + расширение **MLDSL Helper** (подсказки/hover/F12).

## 1) Установи MLDSL

Скачай и запусти установщик из Releases.

Рекомендуемые галочки:

- “Добавить `mldsl` в PATH”
- “Контекстное меню проводника для `.mldsl`”
- “Установить расширение VS Code” (если VS Code установлен)

## 2) Создай файл `.mldsl`

Пример:

```mldsl
event("Вход игрока") {
    player.message("Привет!")
}
```

## 3) Скомпилируй в `plan.json`

### Вариант A (контекстное меню)

ПКМ по файлу `.mldsl` → “MLDSL: Скомпилировать в plan.json”.

Результат записывается в:

- `%APPDATA%\\.minecraft\\plan.json`

### Вариант B (командой)

```powershell
mldsl compile test.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"
```

## 4) Запусти в игре

В Minecraft (в чате):

```
/mldsl run "%APPDATA%\.minecraft\plan.json"
```

## 5) VS Code (подсказки)

Если авто‑установка расширения не сработала:

1) Открой VS Code
2) Extensions → “Install from VSIX…”
3) Выбери `mldsl-helper.vsix` (его можно скачать из релиза или собрать локально)

