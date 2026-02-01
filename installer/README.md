# Инсталлер (Windows)

Схема: **1 exe + (опционально) Inno Setup installer**.

## Что ставит инсталлер

- `mldsl.exe` в `{Program Files}\MLDSL`
- read-only ассеты в `{Program Files}\MLDSL\assets\`
  - `Aliases.json`, `LangTokens.json`, `allactions.txt`
- (опционально) добавляет `mldsl` в `PATH`
- (опционально) добавляет пункт контекстного меню для `.mldsl`:
  - компиляция в `%APPDATA%\.minecraft\plan.json`

Все **генерируемые файлы** (`out/api_aliases.json`, `out/docs`, кеши, логи) по умолчанию идут в:

- `%LOCALAPPDATA%\MLDSL\...`

Portable-режим:

- `MLDSL_PORTABLE=1` или файл `portable.flag` рядом с exe → данные в `<папка_с_exe>\MLDSL\...`

## Сборка exe

Рекомендуемый entrypoint для сборки: `mldsl_cli.py`.

Минимум для работы компилятора: сначала сгенерировать `out/`:

```powershell
python tools\build_all.py
```

## Сборка инсталлера

Открой `installer/MLDSL.iss` в Inno Setup Compiler и собери.

