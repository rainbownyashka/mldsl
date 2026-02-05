# AI Bench (RU) — IR режим в `tools/_premium/ai_coder.py`

Цель: заставить локальные модели **не галлюцинировать** и писать валидный MLDSL/plan через жёсткий промежуточный формат.

## Главная идея (что реально даёт результат)

1) Модель генерирует **только JSON IR** (`ops[]`) — никаких tool calls и никакого MLDSL напрямую.
2) Скрипт валидирует/компилирует IR детерминированно через builder‑tools:
   - `create_file` → `begin_event` → `add_action` → `end_event` → `save_program`
3) Для Ollama используется `format=json`, чтобы модель физически держалась в валидном JSON.
4) При ошибках — ретраи с передачей текста ошибки в `[IR_ERRORS]`.

Это снимает основной класс проблем: «модель пишет псевдокод», «выдумывает синтаксис», «ломает tool protocol».

## Что починено по пути

- `tools/mldsl_compile.py`: добавлен `sys.path.insert(0, repo_root)`, иначе wrapper мог падать с `ModuleNotFoundError: mldsl_paths` при компиляции из подпроцессов.
- `mldsl_compile.py:load_known_events()`: детект событий теперь по подстрокам (`"событие" + "игрока"/"мира"`) вместо жёсткого сравнения, чтобы было устойчивее к вариантам текста.
- IR‑компилятор:
  - автоматически делает `get_sig` для всех использованных `module.func` перед `save_program` (у `ai_coder.py` есть safety‑gate).
  - маппит частые названия событий (`player.enter`, `player_join`, `enter`, `join`) → `вход`, аналогично для `leave/quit` → `выход`.
  - каждый retry пишет в **новый файл** `ir_main_N.mldsl`, чтобы не ломать stack незакрытыми блоками при ошибках.

## Smoke‑тест (prompt)

Файл: `tools/_premium/prompts/ir_smoke_ru.prompt`  
Смысл: «событие вход + отправить сообщение».

## Результаты (минимум 3 модели)

Проверка: `uv run tools/_premium/ai_coder.py agent --ir --prompt-file tools/_premium/prompts/ir_smoke_ru.prompt --model <MODEL> --max-steps 3 --allow-write --debug`

- `qwen2.5-coder:7b` — PASS (с маппингом event → `вход`)
- `qwen3-coder` — PASS (с маппингом event → `вход`)
- `qwen2.5-coder:3b-instruct-q4_K_M` — PASS (с маппингом event → `вход`)

Наблюдение: `deepseek-r1:8b` часто уходит в долгую генерацию, 120s timeout может быть недостаточен без `--ollama-timeout`.

## Дальше (что улучшать)

- IR схема для `if/else`, `select`, `loop`, `func/call`, return/args.
- Прямой список допустимых событий в IR‑подсказке (или отдельный tool `list_events` из `actions_catalog.json`).
- Для “невозможности” невалидного вывода сильнее, чем `format=json`:
  - в будущем можно подключить настоящую grammar‑констрейнт декодировку (Outlines/Guidance/llama.cpp grammar),
    но сейчас практический выигрыш уже даёт `format=json` + валидатор + ретраи.

