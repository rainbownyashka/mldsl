# MLDSL — быстрый старт (RU)

## 0) Что нужно

- Мод BetterCode (MLBetterCode) для Minecraft 1.12.2 Forge (печатает `plan.json` через `/mldsl run`):
  - https://github.com/rainbownyashka/mlbettercode
- MLDSL (компилятор `.mldsl` → `plan.json`):
  - скачай установщик или `mldsl.exe` из Releases: https://github.com/rainbownyashka/mldsl/releases

Опционально (очень рекомендуется):
- VS Code + расширение **MLDSL Helper** (автодополнение, hover, F12).
  - Установщик может поставить расширение автоматически, либо можно вручную “Install from VSIX”.

## 1) Напиши код `.mldsl`

Пример:

```mldsl
event("Вход игрока") {
    player.message("Привет!")
}
```

## 2) Скомпилируй в `plan.json`

### Вариант A — через контекстное меню Проводника (если включено в установщике)

ПКМ по файлу `.mldsl` → **MLDSL: Скомпилировать в plan.json**.

По умолчанию пишет в:
- `%APPDATA%\\.minecraft\\plan.json`

### Вариант B — через команду

```powershell
mldsl compile test.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"
```

## 3) Распечатай план в игре

В Minecraft (в чате):

```
/mldsl run "%APPDATA%\.minecraft\plan.json"
```

