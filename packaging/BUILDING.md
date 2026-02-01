# Сборка установщика (Windows)

Этот репозиторий умеет собирать установщик, который содержит:

- `mldsl.exe` (скомпилированный CLI);
- read-only assets (`Aliases.json`, `LangTokens.json`, `allactions.txt`);
- seed-снапшот `out/` (доки + api_aliases), чтобы всё работало сразу после установки;
- опционально VSCode расширение `mldsl-helper.vsix`.

## 1) Подготовка payload

Payload — это папка `dist/payload/...`, которую потом забирает Inno Setup (`installer/MLDSL.iss`).

Локально (с пересборкой `out/` из твоего `.minecraft/regallactions_export.txt` и `apples.txt`):

```powershell
python packaging\prepare_installer_payload.py
```

Для CI/релиза (без локальных файлов, строго из снапшота `seed/out`):

```powershell
python packaging\prepare_installer_payload.py --use-seed
```

## 2) Сборка установщика (Inno Setup)

```powershell
iscc installer\MLDSL.iss
```

Готовый установщик появится в `dist/release/`.

## 3) VSCode расширение (опционально)

```powershell
cd tools/mldsl-vscode
npm ci
vsce package --no-dependencies -o ../../dist/payload/mldsl-helper.vsix
```

Если `dist/payload/mldsl-helper.vsix` существует, установщик предложит авто-установку расширения.

