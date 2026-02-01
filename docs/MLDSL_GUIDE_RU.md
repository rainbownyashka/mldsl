# MLDSL — гайд (RU)

## Что это

MLDSL компилирует `.mldsl` в JSON‑план (`plan.json`) для печати/исполнения через мод BetterCode в Minecraft.

## Главный поток

1) Пишешь `.mldsl`
2) Компилируешь в `plan.json`
3) В Minecraft запускаешь `/mldsl run <plan.json>`

## Установка (Windows)

Установщик из Releases ставит:

- `mldsl.exe` (компилятор/CLI);
- `assets/` (read‑only файлы, нужные компилятору);
- seed‑`out/` в `%LOCALAPPDATA%\\MLDSL\\out` (доки и api‑алиасы), чтобы всё работало сразу.

### Контекстное меню проводника

Если включить опцию “Контекстное меню проводника”, у `.mldsl` появится пункт:

- **MLDSL: Скомпилировать в plan.json** — компилирует выбранный файл в:
  - `%APPDATA%\\.minecraft\\plan.json`

Это удобно, когда нужно быстро “собрать и вставить в игру” без терминала.

## Команды CLI

### Компиляция

```powershell
mldsl compile file.mldsl --plan "%APPDATA%\\.minecraft\\plan.json"
```

### Печать плана в stdout (для дебага)

```powershell
mldsl compile file.mldsl --print-plan
```

### Показ путей (куда складываются `out/`, `assets/` и т.п.)

```powershell
mldsl paths
```

## VS Code (подсказки)

Расширение **MLDSL Helper** даёт:

- подсказки функций/аргументов,
- hover с документацией,
- F12 “Go to Definition” в сгенерированные доки.

Авто‑установка возможна из установщика (если VS Code найден). Если нет — ставится вручную через VSIX.

## Для разработчика: пересборка API/доков

Если у тебя есть локальные экспорты (`regallactions_export.txt`, `apples.txt`), можно пересобрать `out/`:

```powershell
python tools/build_all.py
```

CI/релизы собираются без локальных файлов — из снапшота `seed/out/` (см. `seed/README.md`).

