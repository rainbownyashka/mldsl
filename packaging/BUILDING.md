# Сборка (Windows)

Этот документ — для разработчиков, которые хотят собрать `mldsl.exe`, VS Code расширение и установщик.

## Требования

- Windows 10/11 x64
- Python 3.13+
- Node.js 20+
- Inno Setup 6 (установщик)

Установка через `winget` (по желанию):

```powershell
winget install -e --id Python.Python.3.13
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id JRSoftware.InnoSetup
```

Для Nuitka также нужен компилятор C/C++ (MSVC). Самый простой вариант:

```powershell
winget install -e --id Microsoft.VisualStudio.2022.BuildTools
```

## 1) Собрать VS Code расширение (VSIX)

```powershell
cd tools/mldsl-vscode
npm ci
npx --yes @vscode/vsce package --no-dependencies -o ../../dist/payload/mldsl-helper.vsix
```

## 2) Подготовить payload для установщика

Payload кладётся в `dist/payload/` и включает:
- `app/` (standalone сборка `mldsl.exe` + зависимости)
- `assets/` (read-only файлы: `Aliases.json`, `LangTokens.json`, `allactions.txt`)
- `seed_out/` (предсобранный `out/`, чтобы пользователю не нужен был Python/экспорты)
- (опционально) `mldsl-helper.vsix`

### Режим для CI/релизов (без экспортов из игры)

```powershell
python packaging/prepare_installer_payload.py --use-seed
```

Этот режим использует snapshot `seed/out/` (см. `seed/README.md`).

### Режим для разработки (пересобрать `out/` из локальных экспортов)

Нужно, чтобы существовал экспорт:
- `%APPDATA%\\.minecraft\\regallactions_export.txt`
  - или переменная `MLDSL_REGALLACTIONS_EXPORT=<путь>`

```powershell
python packaging/prepare_installer_payload.py
```

## 3) Собрать установщик (Inno Setup)

```powershell
iscc installer/MLDSL.iss
```

Готовый установщик окажется в `dist/release/`.
