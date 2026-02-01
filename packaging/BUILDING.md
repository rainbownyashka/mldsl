# Сборка `mldsl.exe`

В репозитории есть entrypoint `mldsl_cli.py` (команды `build-all`, `compile`, `paths`).

## Быстрый путь (для релиза + инсталлер)

Собирает всё, что нужно Inno Setup (`dist/payload/...`):

```powershell
python packaging\prepare_installer_payload.py
```

## Вариант A (рекомендую): Nuitka standalone

Плюсы:
- не нужен Python на ПК пользователя (если собирать `--standalone`)
- обычно меньше “pyinstaller-вирус” ложных срабатываний (но зависит от AV)

Минусы:
- сборка дольше, чем PyInstaller

Пример:

```powershell
python -m pip install -U nuitka
python -m nuitka mldsl_cli.py `
  --standalone `
  --assume-yes-for-downloads `
  --output-dir=dist `
  --output-filename=mldsl.exe
```

В Inno Setup лучше класть **standalone папку**, а не onefile.

## Вариант B: PyInstaller one-dir

Плюсы:
- проще/быстрее сборка

Минусы:
- чаще ложные срабатывания AV

```powershell
python -m pip install -U pyinstaller
pyinstaller --noconfirm --clean --onedir --name mldsl mldsl_cli.py
```

## Важно про ассеты

Инсталлер кладёт эти файлы в `{app}\\assets\\`:

- `Aliases.json`
- `LangTokens.json`
- `allactions.txt`

Компилятор ищет их сначала в репозитории, потом рядом с exe (`assets/`), потом в `%LOCALAPPDATA%\\MLDSL\\assets`.
