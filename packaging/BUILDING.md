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

Примечания:
- В релизах VSIX (`dist/payload/mldsl-helper.vsix`) обязателен и встраивается в установщик.
- Для dev-сборки без VSIX можно собрать так:
  ```powershell
  iscc installer/MLDSL.iss /DNoVsix=1
  ```

## 4) Публикация расширения (автообновления)

Если расширение опубликовано в Marketplace/OpenVSX, VS Code будет обновлять его автоматически.
Но это *не обязательно*, потому что установщик MLDSL уже умеет ставить VSIX оффлайн.

Варианты:

- **VS Code Marketplace** (автообновления “из коробки”)
  - Нужно: аккаунт издателя + токен.
  - Понадобится поменять `publisher` в `tools/mldsl-vscode/package.json` (сейчас `local`).
  - Команда: `npx --yes @vscode/vsce publish`

- **OpenVSX** (часто проще, работает в VSCodium)
  - Нужно: токен OpenVSX.
  - Команда: `npx --yes ovsx publish -p <TOKEN>`

Рекомендация:
- Для новичков/оффлайна — **держать VSIX внутри установщика**.
- Для продвинутых — дополнительно публиковать в OpenVSX/Marketplace.
