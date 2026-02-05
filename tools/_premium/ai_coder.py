import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
API_ALIASES = REPO_ROOT / "out" / "api_aliases.json"
DOCS_ROOT = REPO_ROOT / "out" / "docs"


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _ansi(code: str) -> str:
    return f"\x1b[{code}m"


def _supports_ansi() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return True


def _fmt(color_code: str, text: str) -> str:
    if not _supports_ansi():
        return text
    return _ansi(color_code) + text + _ansi("0")


def norm_ident(s: str) -> str:
    t = (s or "").strip().lower()
    for ch in ("_", " ", "-", "\t"):
        t = t.replace(ch, "")
    return t


def strip_strings_and_comments(src: str) -> str:
    out: list[str] = []
    in_str = False
    esc = False
    for ch in src:
        if in_str:
            if esc:
                esc = False
                out.append(" ")
                continue
            if ch == "\\":
                esc = True
                out.append(" ")
                continue
            if ch == '"':
                in_str = False
                out.append(" ")
                continue
            out.append(" ")
            continue

        if ch == '"':
            in_str = True
            out.append(" ")
            continue

        out.append(ch)

    # strip # comments line-by-line (after strings removed)
    s = "".join(out)
    lines: list[str] = []
    for line in s.splitlines():
        idx = line.find("#")
        lines.append(line if idx < 0 else line[:idx])
    return "\n".join(lines)


def split_top_level_args(arg_src: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str = False
    esc = False
    for ch in arg_src:
        if in_str:
            cur.append(ch)
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            cur.append(ch)
            continue

        if ch == "(":
            depth += 1
            cur.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
            continue

        if ch == "," and depth == 0:
            part = "".join(cur).strip()
            if part:
                parts.append(part)
            cur = []
            continue

        cur.append(ch)

    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def strip_markdown_code_fence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return s

MODULE_ALIASES = {
    "player": "player",
    "игрок": "player",
    "game": "game",
    "игра": "game",
    "var": "var",
    "перем": "var",
    "переменная": "var",
    "array": "array",
    "массив": "array",
    "if_player": "if_player",
    "ifplayer": "if_player",
    "еслиигрок": "if_player",
    "если_игрок": "if_player",
    "if_game": "if_game",
    "ifgame": "if_game",
    "еслиигра": "if_game",
    "если_игра": "if_game",
    "if_value": "if_value",
    "ifvalue": "if_value",
    "еслипеременная": "if_value",
    "если_переменная": "if_value",
    "misc": "misc",
}


@dataclass(frozen=True)
class ResolvedFunc:
    module: str
    canon: str
    spec: dict


class ApiIndex:
    def __init__(self, api: dict):
        self.api = api

    @classmethod
    def load(cls) -> "ApiIndex":
        if not API_ALIASES.exists():
            raise FileNotFoundError(f"api not found: {API_ALIASES} (run: python tools/build_all.py)")
        return cls(json.loads(API_ALIASES.read_text(encoding="utf-8")))

    def resolve(self, module: str, func: str) -> ResolvedFunc | None:
        mod_key = MODULE_ALIASES.get(norm_ident(module), module)
        mod = self.api.get(mod_key)
        if not mod:
            return None

        if func in mod:
            return ResolvedFunc(mod_key, func, mod[func])

        func_n = norm_ident(func)
        for canon, spec in mod.items():
            aliases = spec.get("aliases") or []
            if func in aliases:
                return ResolvedFunc(mod_key, canon, spec)
            if func_n and (func_n == norm_ident(canon) or any(func_n == norm_ident(a) for a in aliases)):
                return ResolvedFunc(mod_key, canon, spec)
        return None

    def validate_source(self, src: str) -> dict:
        """
        Best-effort static validation:
        - unknown module.func calls
        - unknown keyword arguments (only checks when we can infer allowed names)
        - unknown enum string literals (when enum options are known)
        """
        cleaned = strip_strings_and_comments(src or "")
        call_re = re.compile(r"(?<![\\wА-Яа-я_])([\\wА-Яа-я_]+)\\.([\\wА-Яа-я_]+)\\s*\\(([^)]*)\\)", re.S)
        errors: list[str] = []
        warnings: list[str] = []

        for m in call_re.finditer(cleaned):
            mod_raw, func_raw, args_raw = m.group(1), m.group(2), m.group(3) or ""
            r = self.resolve(mod_raw, func_raw)
            if not r:
                errors.append(f"unknown function: {mod_raw}.{func_raw}")
                continue

            spec = r.spec or {}
            params = spec.get("params") or []
            enums = spec.get("enums") or []
            allowed_kw: set[str] = set()
            for p in params:
                if isinstance(p, dict) and p.get("name"):
                    allowed_kw.add(str(p["name"]))
            for e in enums:
                if isinstance(e, dict) and e.get("name"):
                    allowed_kw.add(str(e["name"]))

            for part in split_top_level_args(args_raw):
                eq = part.find("=")
                if eq <= 0:
                    continue
                key = part[:eq].strip()
                if allowed_kw and key not in allowed_kw:
                    errors.append(
                        f"{r.module}.{r.canon}: unknown kw arg `{key}` (allowed: {', '.join(sorted(allowed_kw))})"
                    )

                # enum string literal check (only when options known and value is a simple "str")
                val = part[eq + 1 :].strip()
                if not (val.startswith('"') and val.endswith('"') and len(val) >= 2):
                    continue
                raw_val = val[1:-1]
                enum = next((e for e in enums if isinstance(e, dict) and e.get("name") == key), None)
                opts = (enum or {}).get("options") if isinstance(enum, dict) else None
                if isinstance(opts, dict) and opts and raw_val not in opts:
                    examples = ", ".join(list(opts.keys())[:10])
                    errors.append(f"enum `{key}`: неизвестное значение `{raw_val}`. Варианты: {examples}")

        return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

    def list_modules(self) -> list[str]:
        return sorted(self.api.keys())

    def list_funcs(self, module: str) -> list[str]:
        mod_key = MODULE_ALIASES.get(norm_ident(module), module)
        mod = self.api.get(mod_key) or {}
        return sorted(mod.keys())

    def doc_markdown(self, r: ResolvedFunc) -> str:
        doc_path = DOCS_ROOT / r.module / f"{r.canon}.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")

        # fallback: format from spec (if docs weren't generated)
        params = r.spec.get("params") or []
        enums = r.spec.get("enums") or []
        aliases = r.spec.get("aliases") or []
        desc = (r.spec.get("description") or "").strip()
        gui = (r.spec.get("gui") or "").strip()
        sign1 = (r.spec.get("sign1") or "").strip()
        sign2 = (r.spec.get("sign2") or "").strip()
        action_id = (r.spec.get("id") or "").strip()

        lines = [f"# `{r.module}.{r.canon}(... )`", ""]
        if gui:
            lines.append(f"- `gui`: `{gui}`")
        lines.append(f"- `sign1`: `{sign1}`")
        lines.append(f"- `sign2`: `{sign2}`")
        lines.append(f"- `id`: `{action_id}`")
        if aliases:
            lines.append("- `aliases`: " + ", ".join(f"`{a}`" for a in aliases))
        lines.append("")
        if desc:
            lines.append("## Description")
            lines.append("```")
            lines.append(desc)
            lines.append("```")
            lines.append("")
        if params:
            lines.append("## Params")
            for p in params:
                lines.append(f"- `{p.get('name','')}`: `{p.get('mode','')}` slot `{p.get('slot')}`")
            lines.append("")
        if enums:
            lines.append("## Enums")
            for e in enums:
                lines.append(f"- `{e.get('name')}`: slot `{e.get('slot')}`")
            lines.append("")
        return "\n".join(lines) + "\n"

def _ensure_under_repo(rel_path: str) -> Path:
    p = Path(rel_path)
    if p.is_absolute():
        raise ValueError("absolute paths are not allowed")
    full = (REPO_ROOT / p).resolve()
    repo = REPO_ROOT.resolve()
    if repo not in full.parents and full != repo:
        raise ValueError("path escapes repo root")
    return full


def parse_use_item(s: str) -> tuple[str, str]:
    # Accept: "module.func" or "module func"
    s = (s or "").strip()
    if "." in s:
        a, b = s.split(".", 1)
        return a.strip(), b.strip()
    parts = s.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    raise ValueError(f"--use expects module.func, got: {s!r}")


def cmd_modules(api: ApiIndex) -> int:
    for m in api.list_modules():
        print(m)
    return 0


def cmd_funcs(api: ApiIndex, module: str) -> int:
    funcs = api.list_funcs(module)
    if not funcs:
        eprint(f"no such module (or empty): {module}")
        return 2
    for f in funcs:
        print(f)
    return 0


def cmd_doc(api: ApiIndex, module: str, func: str) -> int:
    r = api.resolve(module, func)
    if not r:
        eprint(f"not found: {module}.{func}")
        return 2
    print(api.doc_markdown(r))
    return 0


def cmd_ask(api: ApiIndex, question: str, uses: list[str], model_name: str) -> int:
    try:
        from langchain_ollama import ChatOllama
    except Exception as ex:
        eprint("Missing deps. Install:\n  uv pip install -r tools/_premium/requirements.txt")
        eprint(str(ex))
        return 2

    ctx_parts = []
    ctx_parts.append("Ты помощник по MLDSL (русский язык).")
    ctx_parts.append("Пиши только MLDSL-код и краткие пояснения, если надо.")
    ctx_parts.append("Не выдумывай функции: используй только то, что дано в контексте.")
    ctx_parts.append("")
    ctx_parts.append("КОНТЕКСТ:")
    ctx_parts.append(f"- api_aliases: {API_ALIASES}")
    ctx_parts.append(f"- docs_root: {DOCS_ROOT}")
    ctx_parts.append("")

    for u in uses:
        mod, fn = parse_use_item(u)
        r = api.resolve(mod, fn)
        if not r:
            ctx_parts.append(f"## (НЕ НАЙДЕНО) {mod}.{fn}")
            continue
        ctx_parts.append(f"## {r.module}.{r.canon}")
        ctx_parts.append(api.doc_markdown(r).strip())
        ctx_parts.append("")

    prompt = "\n".join(ctx_parts) + "\nВОПРОС:\n" + question.strip()

    llm = ChatOllama(model=model_name, temperature=0)
    msg = llm.invoke(prompt)
    print(getattr(msg, "content", msg))
    return 0


def cmd_agent(
    api: ApiIndex,
    request: str,
    model_name: str,
    max_steps: int,
    allow_write: bool,
    debug: bool,
    *,
    builder_mode: bool = False,
    template: str | None = None,
    ollama_timeout_s: float | None = None,
    ollama_num_predict: int | None = None,
    ollama_num_ctx: int | None = None,
    stream: bool = False,
    debug_full: bool = False,
    keep_alive: int | str | None = None,
    stream_max_silence_s: float | None = None,
    llama_url: str | None = None,
    planner_model: str | None = None,
    planner_llama_url: str | None = None,
    planner_max_tokens: int = 256,
    ir_mode: bool = False,
) -> int:
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        from langchain_core.tools import tool
    except Exception as ex:
        eprint("Missing deps. Install:\n  uv pip install -r tools/_premium/requirements.txt")
        eprint(str(ex))
        return 2

    # ---- session sandbox ----
    sessions_root = REPO_ROOT / "tools" / "_premium" / "_sessions"
    session_id = time.strftime("%Y%m%d_%H%M%S")
    session_dir = (sessions_root / session_id).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    session_rel = session_dir.relative_to(REPO_ROOT.resolve()).as_posix()
    created_files: set[Path] = set()

    # ---- synth mode UI ----
    synth_on = False
    synth_depth = 0

    def _get_response_meta(obj) -> dict | None:
        for attr in ("response_metadata", "metadata"):
            m = getattr(obj, attr, None)
            if isinstance(m, dict) and m:
                return m
        ak = getattr(obj, "additional_kwargs", None)
        if isinstance(ak, dict):
            m = ak.get("response_metadata") or ak.get("metadata")
            if isinstance(m, dict) and m:
                return m
        return None

    def _extract_ollama_counts(meta: dict | None) -> tuple[int | None, int | None]:
        if not meta:
            return None, None
        p = meta.get("prompt_eval_count", None)
        c = meta.get("eval_count", None)
        try:
            p = int(p) if p is not None else None
        except Exception:
            p = None
        try:
            c = int(c) if c is not None else None
        except Exception:
            c = None
        return p, c

    def _infer_ctx_max(meta: dict | None) -> int | None:
        if not meta:
            return None
        for k in (
            "num_ctx",
            "context_length",
            "context_size",
            "ctx_size",
            "max_context_length",
            "max_ctx",
        ):
            v = meta.get(k)
            if v is None:
                continue
            try:
                n = int(v)
            except Exception:
                continue
            if n > 0:
                return n
        return None

    def _fmt_tokens(meta: dict | None, ctx_max: int | None, llm_s: float | None = None) -> str:
        p, c = _extract_ollama_counts(meta)
        ctx_max = ctx_max or _infer_ctx_max(meta)
        if p is None and c is None:
            return f"tokens=n/a (ctx={'n/a' if not ctx_max else ctx_max})"
        total = (p or 0) + (c or 0)
        tps = None
        if llm_s and llm_s > 0 and c is not None:
            try:
                tps = float(c) / float(llm_s)
            except Exception:
                tps = None
        if ctx_max:
            base = f"tokens={total}/{ctx_max} (prompt={p} completion={c})"
        else:
            base = f"tokens={total} (ctx=n/a prompt={p} completion={c})"
        if tps is not None:
            return f"{base} tps={tps:.2f}"
        return base

    def ui_thought(msg: str) -> None:
        # gray
        eprint(_fmt("90", msg))

    def ui_synth(msg: str) -> None:
        # cyan
        eprint(_fmt("96", msg))

    # ---- IR mode (JSON -> deterministic tool calls) ----
    def run_ir_mode() -> int:
        if model_name.startswith(("llama:", "llama_cpp:")):
            eprint("[error] IR mode сейчас поддерживает только Ollama (для строгого JSON через format=json).")
            eprint("Подсказка: запусти Ollama-модель и используй `--model qwen3-coder`/`--model qwen2.5-coder:7b` и т.п.")
            return 2

        ir_system = (
            "Ты генератор IR для MLDSL.\n"
            "Правило: выведи ТОЛЬКО валидный JSON (без markdown, без пояснений).\n"
            "Схема:\n"
            "{\n"
            '  \"ops\": [\n'
            '    {\"op\":\"new_program\"},\n'
            '    {\"op\":\"begin_event\",\"name\":\"...\"},\n'
            '    {\"op\":\"begin_call_block\",\"target\":\"module.func\",\"parameters\":{\"kw\":\"value\"}},\n'
            '    {\"op\":\"add_action\",\"target\":\"module.func\",\"parameters\":{\"kw\":\"value\"}},\n'
            '    {\"op\":\"end_call_block\"},\n'
            '    {\"op\":\"end_event\"},\n'
            '    {\"op\":\"save_program\"}\n'
            "  ]\n"
            "}\n"
            "Где:\n"
            "- target всегда строка вида module.func (например player.message)\n"
            "- parameters: объект keyword-аргументов (только те, что реально существуют)\n"
            "- begin_call_block/end_call_block: открывает/закрывает блок условия вида if_player.имеет_право(...) { ... }\n"
            "Нельзя добавлять другие поля/структуры.\n"
        )

        def _ollama_chat_json(model: str, sys_text: str, user_text: str) -> str:
            # Native Ollama endpoint. We use format=json to strongly bias to valid JSON output.
            url = "http://127.0.0.1:11434/api/chat"
            payload: dict[str, Any] = {
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": sys_text},
                    {"role": "user", "content": user_text},
                ],
            }
            options: dict[str, Any] = {}
            if ollama_num_ctx is not None:
                options["num_ctx"] = int(ollama_num_ctx)
            if ollama_num_predict is not None:
                options["num_predict"] = int(ollama_num_predict)
            if options:
                payload["options"] = options
            if keep_alive is not None:
                payload["keep_alive"] = keep_alive
            r = requests.post(url, json=payload, timeout=float(ollama_timeout_s or 120.0))
            r.raise_for_status()
            data = r.json() or {}
            msg = data.get("message") or {}
            return str(msg.get("content") or "")

        def _compile_ops(ops: list[dict], *, out_path: str) -> tuple[bool, str]:
            file_id: str | None = None
            used_funcs: set[tuple[str, str]] = set()

            def need_file_id() -> str:
                nonlocal file_id
                if file_id:
                    return file_id
                res0 = exec_tool_call({"name": "create_file", "args": {"path": out_path}})
                try:
                    data0 = json.loads(res0) if isinstance(res0, str) else {}
                except Exception:
                    data0 = {}
                file_id = str((data0 or {}).get("file_id") or "").strip() or None
                if not file_id:
                    raise ValueError("create_file did not return file_id")
                return file_id

            def tool_ok(res: str) -> bool:
                return not (isinstance(res, str) and (res.startswith("ERROR:") or res.startswith("ERR")))

            try:
                for op in ops:
                    if not isinstance(op, dict):
                        return False, "op is not an object"
                    name = op.get("op")
                    if not name:
                        return False, "missing op field"

                    tc: dict[str, Any]
                    if name == "new_program":
                        # Ignore model-provided path and force a fresh file for this attempt.
                        tc = {"name": "create_file", "args": {"path": out_path}}
                    elif name == "begin_event":
                        raw_name = str(op.get("name") or "Событие").strip()
                        key = raw_name.lower()
                        key = re.sub(r"[^0-9a-zа-я]+", " ", key)
                        key = re.sub(r"\s+", " ", key).strip()
                        mapped = None
                        if key in {
                            "join",
                            "enter",
                            "player enter",
                            "player joined",
                            "player join",
                            "вход",
                            "вход игрока",
                            "событие входа",
                        }:
                            mapped = "вход"
                        elif key in {
                            "leave",
                            "quit",
                            "exit",
                            "player leave",
                            "player quit",
                            "выход",
                            "выход игрока",
                            "событие выхода",
                        }:
                            mapped = "выход"
                        elif key in {"right click", "rightclick", "правый клик", "игрок кликает правой кнопкой"}:
                            mapped = "Правый клик"
                        elif key in {"left click", "leftclick", "левый клик", "игрок кликает левой кнопкой"}:
                            mapped = "Левый клик"
                        ev_name = mapped or raw_name
                        if mapped and debug:
                            eprint(f"[debug][IR] mapped event name: {raw_name!r} -> {ev_name!r}")
                        tc = {"name": "begin_event", "args": {"file_id": need_file_id(), "name": ev_name}}
                    elif name == "begin_call_block":
                        target = op.get("target") or ""
                        params = op.get("parameters") or {}
                        if not target:
                            return False, "begin_call_block missing target"
                        tc = {
                            "name": "begin_call_block",
                            "args": {"file_id": need_file_id(), "target": target, "parameters": params},
                        }
                    elif name == "add_action":
                        target = op.get("target") or ""
                        params = op.get("parameters") or {}
                        if not target:
                            return False, "add_action missing target"
                        tc = {"name": "add_action", "args": {"file_id": need_file_id(), "target": target, "parameters": params}}
                    elif name == "end_call_block":
                        tc = {"name": "end_call_block", "args": {"file_id": need_file_id()}}
                    elif name == "end_event":
                        tc = {"name": "end_event", "args": {"file_id": need_file_id()}}
                    elif name == "save_program":
                        for mod, fn in sorted(used_funcs):
                            _ = exec_tool_call({"name": "get_sig", "args": {"module": mod, "func": fn}})
                        tc = {"name": "save_program", "args": {"file_id": need_file_id()}}
                    elif name == "list_modules":
                        tc = {"name": "list_modules", "args": {}}
                    elif name == "list_funcs":
                        tc = {"name": "list_funcs", "args": {"module": op.get("module") or ""}}
                    elif name == "get_sig":
                        tc = {"name": "get_sig", "args": {"module": op.get("module") or "", "func": op.get("func") or ""}}
                    else:
                        return False, f"unknown op: {name}"

                    res = exec_tool_call(tc)
                    if debug:
                        eprint(f"[debug][IR] {name} -> {res[:400] if isinstance(res,str) else res}")
                    if not tool_ok(res):
                        return False, str(res)
                    if name == "new_program":
                        try:
                            data = json.loads(res) if isinstance(res, str) else {}
                        except Exception:
                            data = {}
                        fid = str((data or {}).get("file_id") or "").strip()
                        if fid:
                            file_id = fid
                    if name == "add_action":
                        try:
                            data = json.loads(res) if isinstance(res, str) else {}
                        except Exception:
                            data = {}
                        mod = str((data or {}).get("module") or "").strip()
                        fn = str((data or {}).get("func") or "").strip()
                        if mod and fn:
                            used_funcs.add((mod, fn))
                    if name == "begin_call_block":
                        try:
                            data = json.loads(res) if isinstance(res, str) else {}
                        except Exception:
                            data = {}
                        mod = str((data or {}).get("module") or "").strip()
                        fn = str((data or {}).get("func") or "").strip()
                        if mod and fn:
                            used_funcs.add((mod, fn))

                return True, "ok"
            except Exception as ex:
                return False, f"{type(ex).__name__}: {ex}"

        attempts = max(1, int(max_steps or 3))
        last_err = ""
        for attempt in range(1, attempts + 1):
            user_text = request if attempt == 1 else (request + "\n\n[IR_ERRORS]\n" + last_err + "\n[/IR_ERRORS]\nИсправь ошибки и верни новый JSON ops[].")
            content = _ollama_chat_json(model_name, ir_system, user_text)
            try:
                obj = json.loads(strip_markdown_code_fence(content))
            except Exception as ex:
                last_err = f"IR parse failed: {ex}"
                continue
            ops = obj.get("ops")
            if not isinstance(ops, list) or not ops:
                last_err = "ops[] is empty or missing"
                continue
            out_path = f"{session_rel}/ir_main_{attempt}.mldsl"
            ok, err = _compile_ops(ops, out_path=out_path)  # type: ignore[arg-type]
            if ok:
                return 0
            last_err = err

        eprint("[error] IR failed after retries.")
        eprint(last_err[:2000])
        return 2

    def _extract_calls(src: str) -> set[tuple[str, str]]:
        # Rough MLDSL call extractor: matches `module.func(...)` including Cyrillic identifiers.
        calls: set[tuple[str, str]] = set()
        for m in re.finditer(r"(?m)^[ \t]*([\w\u0400-\u04FF]+)\.([\w\u0400-\u04FF]+)\s*\(", src or ""):
            calls.add((m.group(1), m.group(2)))
        return calls

    # ---- constraints inferred from the request ----
    # Best-effort: if user explicitly bans some actions (e.g. "НЕЛЬЗЯ использовать заполнить область"),
    # enforce it at write-time to prevent the model from "cheating".
    req_lower = (request or "").lower()
    banned_tokens: set[str] = set()
    required_substrings: set[str] = set()
    required_aliases: set[str] = set()

    # Lightweight "task lock": when user mentions a specific feature name, require it to appear
    # in the produced MLDSL (prevents the model from drifting to unrelated scripts).
    if re.search(r"\bline\b", req_lower) or "линия" in req_lower or "линию" in req_lower:
        required_substrings.add("line")
    if "postavit_blok" in req_lower or "поставить блок" in req_lower:
        required_aliases.add("postavit_blok")

    if "нельзя" in req_lower or "запрещ" in req_lower:
        # Capture explicit module.func tokens if present.
        for m in re.finditer(r"\b([a-z_]+)\.([a-z_]+)\b", req_lower):
            banned_tokens.add(f"{m.group(1)}.{m.group(2)}")
        # Common Russian mentions that correspond to known actions.
        if "заполнить область" in req_lower or "fill region" in req_lower or "fillregion" in req_lower:
            banned_tokens.update({"zapolnit_oblast", "zapolnit_oblast_blokami", "game.zapolnit_oblast"})
        if "заполнить регион" in req_lower:
            banned_tokens.update({"zapolnit_oblast", "zapolnit_oblast_blokami", "game.zapolnit_oblast"})

    banned_tokens = {t.strip().lower() for t in banned_tokens if t.strip()}
    required_substrings = {t.strip().lower() for t in required_substrings if t.strip()}
    required_aliases = {t.strip().lower() for t in required_aliases if t.strip()}

    template_name = (template or "").strip() or None
    template_marker = f"# TEMPLATE: {template_name}" if template_name else None
    template_base_used_resolved: set[str] = set()
    if template_name:
        required_substrings.add("template:")
        # If we know the template, add a couple of stable anchors to prevent drifting.
        if template_name.lower() == "worldedit_line":
            required_substrings.update({"we_line", "we_line_active"})

        ex_dir = (REPO_ROOT / "examples").resolve()
        cand = (ex_dir / f"{template_name}.mldsl").resolve()
        if not cand.exists():
            raise FileNotFoundError(f"template not found: {cand}")
        tpl_text = cand.read_text(encoding="utf-8", errors="replace")
        if template_marker:
            tpl_text = f"{template_marker}\n" + tpl_text
        # Pre-create main.mldsl in the session.
        main_p = (session_dir / "main.mldsl").resolve()
        main_p.write_text(tpl_text, encoding="utf-8", errors="replace")
        created_files.add(main_p)

        # Compute resolved-call set for the template so we don't require get_sig/get_doc for every template call.
        used = _extract_calls(tpl_text)
        for mod_name, func_name in sorted(used):
            r = api.resolve(mod_name, func_name)
            if not r:
                continue
            spec = r.spec or {}
            template_base_used_resolved.add(f"{r.module}.{r.canon}".lower())
            for a in spec.get("aliases") or []:
                if isinstance(a, str) and a:
                    template_base_used_resolved.add(a.strip().lower())

    # If template is provided but user only wants the template materialized, allow a fast exit.
    if template_name and re.fullmatch(r"\s*(prefill|template|just\s*template)\s*", (request or ""), flags=re.IGNORECASE):
        print(json.dumps({"sessionRel": f"{session_rel}/", "prefilled": "main.mldsl", "template": template_name}, ensure_ascii=False))
        return 0

    # ---- requested output files (for early stop) ----
    def _norm_suffix(p: str) -> str:
        return p.replace("\\", "/").lstrip("./")

    requested_raw: list[str] = [
        _norm_suffix(s) for s in re.findall(r"(?i)\b[\w./-]+\.(?:mldsl|dslpy|dsl\.py)\b", request or "")
    ]
    # If the user explicitly allows either MLDSL or DSLPY, treat a single requested file
    # as an *alternative group* (one of the two extensions is acceptable).
    allow_either_mldsl_or_dslpy = bool(
        re.search(r"(?i)\bmldsl\b", request or "")
        and re.search(r"(?i)\b(dslpy|dsl\.py)\b", request or "")
    )

    requested_groups: list[set[str]] = []
    if allow_either_mldsl_or_dslpy and len(requested_raw) == 1:
        one = requested_raw[0]
        alt: str | None = None
        if one.lower().endswith(".mldsl"):
            alt = one[: -len(".mldsl")] + ".dslpy"
        elif one.lower().endswith(".dslpy"):
            alt = one[: -len(".dslpy")] + ".mldsl"
        elif one.lower().endswith(".dsl.py"):
            alt = one[: -len(".dsl.py")] + ".mldsl"
        if alt:
            requested_groups = [{one, alt}]
        else:
            requested_groups = [{one}]
    else:
        requested_groups = [{s} for s in requested_raw]

    requested_suffixes: set[str] = set().union(*requested_groups) if requested_groups else set()
    # Common pattern: user asks for "файл main.mldsl", model writes into session dir.
    written_suffixes: set[str] = set()
    chosen_suffix_by_group: dict[int, str] = {}

    def _mark_written(rel_or_abs: str) -> bool:
        if not requested_suffixes:
            return False
        norm = rel_or_abs.replace("\\", "/")
        for gi, group in enumerate(requested_groups):
            for suf in group:
                if norm.endswith(suf):
                    written_suffixes.add(suf)
                    chosen_suffix_by_group.setdefault(gi, suf)
        # Satisfied when each requested group has at least one written suffix.
        return bool(requested_groups) and all(any(s in written_suffixes for s in g) for g in requested_groups)

    def _ensure_under_session(rel_path: str) -> Path:
        if not rel_path:
            raise ValueError("path is required")
        norm = rel_path.replace("\\", "/").lstrip("./")
        if "<" in norm or ">" in norm:
            raise ValueError("invalid path placeholder ('<' or '>'); use 'main.mldsl' or another simple relative path inside the session dir")
        # Allow callers to pass either:
        # - "main.mldsl" (preferred; interpreted relative to the session dir)
        # - "<sessionRel>/main.mldsl" (older style)
        if norm.startswith(session_rel + "/"):
            norm = norm[len(session_rel) + 1 :]
        p = Path(norm)
        if p.is_absolute():
            raise ValueError("absolute paths are not allowed")
        full = (session_dir / p).resolve()
        if session_dir not in full.parents and full != session_dir:
            raise ValueError(f"path must be inside session dir: {session_dir}")
        return full

    # ---- tools ----
    looked_up: set[tuple[str, str]] = set()
    tasks: list[dict] = []

    @tool
    def list_modules() -> str:
        "Return list of available API modules."
        return json.dumps(api.list_modules(), ensure_ascii=False, indent=2)

    @tool
    def session_info() -> str:
        "Return the current session directory path(s) for file operations."
        return json.dumps(
            {
                "sessionAbs": str(session_dir),
                "sessionRel": f"{session_rel}/",
            },
            ensure_ascii=False,
            indent=2,
        )

    @tool
    def list_funcs(
        module: str,
        preview_args: int | None = None,
        limit: int | None = None,
        include_aliases: bool | None = None,
    ) -> str:
        """
        Return functions in an API module.

        By default returns a list[str] of canonical function ids.
        If preview_args is provided (>0), returns a list[dict] where each entry includes a compact preview
        of the first N args (params + enums).
        """
        n = 0 if preview_args is None else int(preview_args)
        want_aliases = bool(include_aliases) if include_aliases is not None else False

        if n <= 0 and not want_aliases:
            xs = api.list_funcs(module)
            if limit is not None:
                try:
                    lim = max(0, int(limit))
                except Exception:
                    lim = 0
                if lim > 0:
                    xs = xs[:lim]
            return json.dumps(xs, ensure_ascii=False, indent=2)

        mod_key = MODULE_ALIASES.get(norm_ident(module), module)
        mod = api.api.get(mod_key) or {}
        out: list[dict] = []
        lim = None
        if limit is not None:
            try:
                lim = max(0, int(limit))
            except Exception:
                lim = None
        for canon in sorted(mod.keys())[: (lim if (lim and lim > 0) else None)]:
            spec = mod.get(canon) or {}
            params = spec.get("params") or []
            enums = spec.get("enums") or []

            all_args: list[dict] = []
            for p in params:
                if not isinstance(p, dict):
                    continue
                name = (p.get("name") or "").strip()
                if not name:
                    continue
                all_args.append(
                    {
                        "kind": "param",
                        "name": name,
                        "type": (p.get("mode") or "").strip() or None,
                    }
                )
            for e in enums:
                if not isinstance(e, dict):
                    continue
                name = (e.get("name") or "").strip()
                if not name:
                    continue
                options = e.get("options")
                opts_list: list[str] | None = None
                if isinstance(options, dict) and options:
                    opts_list = list(options.keys())
                all_args.append(
                    {
                        "kind": "enum",
                        "name": name,
                        "type": "ENUM",
                        "options": opts_list[:10] if opts_list else None,
                    }
                )

            first = all_args[: max(0, n)]
            preview_parts: list[str] = []
            for a in first:
                t = a.get("type")
                if t and t != "ENUM":
                    preview_parts.append(f"{a['name']}: {t}")
                else:
                    preview_parts.append(f"{a['name']}")
            more = "..." if len(all_args) > len(first) else ""
            preview = f"{canon}(" + ", ".join(preview_parts + ([more] if more else [])) + ")"

            row: dict = {"func": canon, "preview": preview}
            if n > 0:
                row["firstArgs"] = first
                row["totalArgs"] = len(all_args)
            if want_aliases:
                aliases = spec.get("aliases") or []
                row["aliases"] = aliases[:30] if isinstance(aliases, list) else []
            out.append(row)

        return json.dumps(out, ensure_ascii=False, indent=2)

    @tool
    def list_functions(module: str | None = None) -> str:
        "Alias for list_funcs(). Accepts module=...; when omitted, returns an error hint."
        m = (module or "").strip()
        if not m:
            return "ERROR: module is required. Use list_modules() then list_functions(module=...)."
        return list_funcs(m)

    @tool
    def list_files() -> str:
        "List files currently present in the session directory (relative paths)."
        files: list[dict] = []
        for p in session_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(session_dir).as_posix()
                try:
                    sz = p.stat().st_size
                except Exception:
                    sz = None
                files.append({"path": rel, "bytes": sz})
        files.sort(key=lambda x: x["path"])
        return json.dumps(files, ensure_ascii=False, indent=2)

    @tool
    def list_templates() -> str:
        "Return list of available dslpy templates (from examples/*.dslpy)."
        ex_dir = (REPO_ROOT / "examples").resolve()
        names: list[str] = []
        if ex_dir.exists():
            for p in ex_dir.glob("*.dslpy"):
                names.append(p.stem)
        names.sort()
        return json.dumps(names, ensure_ascii=False, indent=2)

    @tool
    def get_template(name: str | None = None, template_name: str | None = None) -> str:
        "Return the content of examples/<name>.dslpy (accepts name=... or template_name=...)."
        raw = (name or template_name or "").strip()
        if not raw:
            return "ERROR: name is required"
        safe = Path(raw).name
        p = (REPO_ROOT / "examples" / f"{safe}.dslpy").resolve()
        if REPO_ROOT.resolve() not in p.parents:
            return "ERROR: invalid template path"
        if not p.exists():
            return f"NOT_FOUND: {safe}"
        return p.read_text(encoding="utf-8", errors="replace")

    @tool
    def get_doc(module: str, func: str) -> str:
        "Return markdown documentation for a function (resolves aliases)."
        r = api.resolve(module, func)
        if not r:
            return f"NOT_FOUND: {module}.{func}"
        looked_up.add((r.module, r.canon))
        text = api.doc_markdown(r)
        # Keep it bounded (tool output can explode context).
        if len(text) > 12000:
            text = text[:12000] + "\n\n...(truncated)\n"
        return text

    @tool
    def get_sig(module: str, func: str) -> str:
        "Return JSON signature (params + enums with options) for a function (resolves aliases)."
        r = api.resolve(module, func)
        if not r:
            return f"NOT_FOUND: {module}.{func}"
        looked_up.add((r.module, r.canon))
        spec = r.spec or {}
        out = {
            "module": r.module,
            "func": r.canon,
            "aliases": spec.get("aliases") or [],
            "menu": spec.get("menu") or "",
            "gui": spec.get("gui") or "",
            "sign1": spec.get("sign1") or "",
            "sign2": spec.get("sign2") or "",
            "description": spec.get("description") or "",
            "params": spec.get("params") or [],
            "enums": spec.get("enums") or [],
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    @tool
    def search_api(
        query: str,
        limit: int = 20,
        by_fullname: bool = True,
        by_aliases: bool = True,
        by_gui: bool = True,
        by_sign: bool = True,
        by_description: bool = True,
        exact: bool = False,
    ) -> str:
        """
        Search across the API by name/aliases/gui/sign/description (toggleable).

        Args:
          - query: text to search
          - limit: max results
          - by_fullname: match "module.func"
          - by_aliases: match aliases
          - by_gui: match GUI title (container title)
          - by_sign: match sign2 (block display name on sign)
          - by_description: match description text
          - exact: if true, only exact matches for fullname/aliases/sign/gui (case-insensitive)

        Returns JSON list of matches:
          [{module, func, aliases, sign2, gui, description, score}]
        """
        q = (query or "").strip().lower()
        if not q:
            return "[]"

        def _norm(s: str) -> str:
            return (s or "").strip().lower()

        def has(s: str) -> bool:
            s2 = _norm(s)
            if not s2:
                return False
            if exact:
                return s2 == q
            return q in s2

        out: list[dict] = []
        for mod, funcs in api.api.items():
            if not isinstance(funcs, dict):
                continue
            for fn, spec in funcs.items():
                if not isinstance(spec, dict):
                    continue
                aliases = [a for a in (spec.get("aliases") or []) if isinstance(a, str)]
                gui = str(spec.get("gui") or "")
                sign2 = str(spec.get("sign2") or "")
                desc = str(spec.get("description") or "")

                score = 0
                if by_fullname and has(f"{mod}.{fn}"):
                    score += 40 if exact else 26
                if by_aliases:
                    if any(_norm(a) == q for a in aliases):
                        score += 35
                    if not exact and any(has(a) for a in aliases):
                        score += 18
                if by_sign and has(sign2):
                    score += 18 if exact else 12
                if by_gui and has(gui):
                    score += 14 if exact else 10
                if by_description and (not exact) and has(desc[:600]):
                    score += 6

                if score <= 0:
                    continue

                out.append(
                    {
                        "module": mod,
                        "func": fn,
                        "aliases": aliases[:8],
                        "sign2": sign2,
                        "gui": gui,
                        "description": (desc[:240] + ("..." if len(desc) > 240 else "")) if desc else "",
                        "score": score,
                    }
                )

        out.sort(key=lambda x: (-int(x.get("score", 0)), x.get("module", ""), x.get("func", "")))
        return json.dumps(out[: max(1, int(limit))], ensure_ascii=False, indent=2)

    @tool
    def check_compilation(path: str | None = None, file_id: str | None = None) -> str:
        """Compile a .mldsl file using tools/mldsl_compile.py and return stdout/stderr + status.
        Accepts:
        - path: workspace-relative/absolute path
        - file_id: builder file id returned by new_program/create_file
        """
        use_path = (path or "").strip()
        if not use_path and file_id:
            bf = _builder_files.get(str(file_id))
            if bf:
                use_path = bf.out_path
        if not use_path:
            return "ERROR: check_compilation requires path or file_id"
        p = _ensure_under_repo(use_path)
        if not p.exists():
            return f"ERROR: file not found: {use_path}"
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "mldsl_compile.py"), str(p), "--print-plan"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        entries_count = None
        empty_plan = None
        try:
            plan = json.loads(proc.stdout or "{}")
            entries = plan.get("entries") if isinstance(plan, dict) else None
            if isinstance(entries, list):
                entries_count = len(entries)
                empty_plan = entries_count == 0
        except Exception:
            pass
        out = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "entriesCount": entries_count,
            "emptyPlan": empty_plan,
            "stdout": (proc.stdout or "")[-8000:],
            "stderr": (proc.stderr or "")[-8000:],
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    @tool
    def read_file(path: str, max_chars: int = 8000) -> str:
        "Read a UTF-8 text file under the current session dir only (bounded)."
        p = _ensure_under_session(path)
        if not p.exists():
            return f"ERROR: file not found: {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n...(truncated)\n"
        return text

    @tool
    def validate_mldsl(content: str | None = None, code: str | None = None) -> str:
        "Validate MLDSL source (unknown functions/kwargs/enums). Args: content (preferred) or code. Returns JSON {ok, errors, warnings}."
        src = content if content is not None else (code or "")
        out = api.validate_source(src or "")
        return json.dumps(out, ensure_ascii=False, indent=2)

    @tool
    def enter_synthesis(reason: str | None = None) -> str:
        "Mark entering SYNTHESIS mode (building a missing primitive from existing actions)."
        nonlocal synth_on, synth_depth
        synth_on = True
        synth_depth += 1
        r = (reason or "").strip()
        ui_synth(f"★ SYNTHESIS ON#{synth_depth}" + (f": {r}" if r else ""))
        return "OK"

    @tool
    def exit_synthesis(summary: str | None = None) -> str:
        "Mark exiting SYNTHESIS mode."
        nonlocal synth_on
        synth_on = False
        s = (summary or "").strip()
        ui_synth("★ SYNTHESIS OFF" + (f": {s}" if s else ""))
        return "OK"

    @tool
    def log_thought(text: str | None = None, content: str | None = None) -> str:
        "Print a short thought/status line (gray)."
        t = (text if text is not None else content) or ""
        t = t.strip()
        if t:
            ui_thought(f"· {t}")
        return "OK"

    @tool
    def create_tasks(items: list | None = None, tasks_list: list | None = None) -> str:
        """
        Create/replace the current task list.

        Accepts:
        - items: ["title1", "title2", ...] (preferred)
        - items: [{"title": "..."}, ...] (tolerated for weaker models)
        - tasks_list: alias for items
        """
        nonlocal tasks
        src = items if items is not None else (tasks_list or [])
        if not isinstance(src, list):
            return "ERROR: items must be a list"

        titles: list[str] = []
        for x in src:
            if isinstance(x, str):
                t = x
            elif isinstance(x, dict):
                t = str(x.get("title") or x.get("text") or x.get("name") or "").strip()
            else:
                t = ""
            if t.strip():
                titles.append(t.strip())

        if not titles:
            return "ERROR: items must contain at least 1 non-empty title string"

        tasks = []
        for i, title in enumerate(titles, start=1):
            tasks.append({"id": i, "title": title, "status": "todo", "notes": []})
        return json.dumps(tasks, ensure_ascii=False, indent=2)

    @tool
    def list_tasks() -> str:
        "Return current task list (id/title/status)."
        return json.dumps(tasks, ensure_ascii=False, indent=2)

    @tool
    def update_task(task_id: int, status: str | None = None, note: str | None = None) -> str:
        "Update a task. status in {todo, doing, done, blocked}. note appends to notes."
        st = (status or "").strip().lower() if status is not None else ""
        if status is not None and st not in {"todo", "doing", "done", "blocked"}:
            return "ERROR: invalid status (use todo/doing/done/blocked)"
        tid = int(task_id)
        for t in tasks:
            if int(t.get("id", -1)) == tid:
                if status is not None:
                    t["status"] = st
                if note:
                    t.setdefault("notes", [])
                    t["notes"].append(str(note))
                return json.dumps(t, ensure_ascii=False, indent=2)
        return f"NOT_FOUND: task_id={tid}"

    @tool
    def resolve_target(target: str) -> str:
        """
        Resolve a function by a single string like 'module.func' (aliases ok).

        Returns a get_sig()-like JSON when resolved, otherwise returns JSON list of search hits.
        Do NOT call other tools from inside this tool (StructuredTool is not callable); query ApiIndex directly.
        """
        raw = (target or "").strip()
        if not raw:
            return "ERROR: target is required"
        mod = ""
        fn = ""
        if "." in raw:
            mod, fn = raw.split(".", 1)
        elif " " in raw:
            parts = [p for p in raw.split() if p]
            if len(parts) >= 2:
                mod, fn = parts[0], parts[1]
        if not (mod and fn):
            return "ERROR: target must be 'module.func'"

        r = api.resolve(mod, fn)
        if r:
            looked_up.add((r.module, r.canon))
            spec = r.spec or {}
            out = {
                "module": r.module,
                "func": r.canon,
                "aliases": spec.get("aliases") or [],
                "menu": spec.get("menu") or "",
                "gui": spec.get("gui") or "",
                "sign1": spec.get("sign1") or "",
                "sign2": spec.get("sign2") or "",
                "description": spec.get("description") or "",
                "params": spec.get("params") or [],
                "enums": spec.get("enums") or [],
            }
            return json.dumps(out, ensure_ascii=False, indent=2)

        q = raw.lower()

        def _norm(s: str) -> str:
            return (s or "").strip().lower()

        def has(s: str) -> bool:
            s2 = _norm(s)
            return bool(s2) and q in s2

        hits: list[dict] = []
        for m2, funcs in api.api.items():
            if not isinstance(funcs, dict):
                continue
            for f2, spec in funcs.items():
                if not isinstance(spec, dict):
                    continue
                aliases = [a for a in (spec.get("aliases") or []) if isinstance(a, str)]
                gui = str(spec.get("gui") or "")
                sign2 = str(spec.get("sign2") or "")
                desc = str(spec.get("description") or "")
                score = 0
                if has(f"{m2}.{f2}"):
                    score += 26
                if any(has(a) for a in aliases):
                    score += 18
                if has(sign2):
                    score += 12
                if has(gui):
                    score += 10
                if has(desc[:600]):
                    score += 6
                if score <= 0:
                    continue
                hits.append(
                    {
                        "module": m2,
                        "func": f2,
                        "aliases": aliases[:12],
                        "sign2": sign2,
                        "gui": gui,
                        "description": desc[:300],
                        "score": score,
                    }
                )
        hits.sort(key=lambda x: (-int(x.get("score", 0)), x.get("module", ""), x.get("func", "")))
        return json.dumps(hits[:10], ensure_ascii=False, indent=2)

    @tool
    def dump_module(module: str, limit: int = 200) -> str:
        "Return a compact dump of an API module (funcs + short signature info)."
        mod = (module or "").strip()
        if not mod:
            return "ERROR: module is required"
        mod_key = MODULE_ALIASES.get(norm_ident(mod), mod)
        m = api.api.get(mod_key)
        if not isinstance(m, dict) or not m:
            return f"NOT_FOUND: module {module}"
        out: list[dict] = []
        for canon, spec in m.items():
            if not isinstance(spec, dict):
                continue
            aliases = spec.get("aliases") or []
            params = spec.get("params") or []
            enums = spec.get("enums") or []
            out.append(
                {
                    "func": canon,
                    "aliases": [a for a in aliases[:6] if isinstance(a, str)],
                    "gui": spec.get("gui") or "",
                    "sign2": spec.get("sign2") or "",
                    "params": [p.get("name") for p in params if isinstance(p, dict) and p.get("name")][:12],
                    "enums": [e.get("name") for e in enums if isinstance(e, dict) and e.get("name")][:12],
                }
            )
        out.sort(key=lambda x: x.get("func", ""))
        return json.dumps(out[: max(1, int(limit))], ensure_ascii=False, indent=2)

    def _write_file_impl(path: str, content: str) -> str:
        # Enforce requested filenames: if the user asked for specific *.mldsl/*.dslpy,
        # the agent must write those (prevents "helpfully" writing a different file).
        if requested_suffixes:
            normp = (path or "").replace("\\", "/")
            if not any(normp.endswith(suf) for suf in requested_suffixes):
                raise ValueError("write_file path must match requested file(s): " + ", ".join(sorted(requested_suffixes)))
            # If the request allows either .mldsl or .dslpy for a single basename,
            # prevent writing both user-visible variants in the same session.
            if allow_either_mldsl_or_dslpy and len(requested_groups) == 1 and len(next(iter(requested_groups))) > 1:
                group = next(iter(requested_groups))
                match = next((suf for suf in group if normp.endswith(suf)), None)
                if match:
                    already = chosen_suffix_by_group.get(0)
                    if already and already != match:
                        raise ValueError(f"choose ONE file type: already wrote {already}, cannot also write {match}")

        p = _ensure_under_session(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p not in created_files:
            raise ValueError("can only modify files created in this session")
        text = strip_markdown_code_fence(content or "")
        is_dslpy = p.suffix.lower() in (".dslpy",) or p.name.lower().endswith(".dsl.py")
        is_mldsl = p.suffix.lower() == ".mldsl"

        # dslpy: transpile -> validate -> compile generated MLDSL sibling (but still store original dslpy).
        if is_dslpy:
            # Allow a very small "template directive" for weak models:
            #   @import timer_start
            #   @template hold_rightclick
            # This is NOT valid python syntax, so we expand it before AST parsing.
            directive_line = ""
            for ln in (text or "").lstrip("\ufeff").splitlines():
                stripped = ln.strip()
                if not stripped:
                    continue
                directive_line = stripped
                break
            m = re.match(r"^@(import|template)\s+(.+?)\s*$", directive_line, flags=re.IGNORECASE)
            if m:
                raw_name = m.group(2).strip()
                raw_name = raw_name.split("#", 1)[0].strip().strip("\"'").replace("\\", "/")
                # tolerate junk after the template name (weak models): "@import timer_start 2"
                raw_name = raw_name.split()[0] if raw_name.split() else raw_name
                name = raw_name.split("/")[-1]
                safe = re.sub(r"[^0-9A-Za-z_.-]", "", name)
                ex_path = (REPO_ROOT / "examples" / f"{safe}.dslpy").resolve()
                if not ex_path.exists():
                    raise ValueError(f"dslpy template not found: {raw_name} (looked for {ex_path})")
                text = ex_path.read_text(encoding="utf-8", errors="replace")

            try:
                import importlib.util

                tp = (REPO_ROOT / "tools" / "_premium" / "dslpy_transpile.py").resolve()
                if not tp.exists():
                    raise FileNotFoundError(str(tp))
                spec = importlib.util.spec_from_file_location("_mldsl_dslpy_transpile", str(tp))
                if not spec or not spec.loader:
                    raise ImportError("spec_from_file_location returned empty spec")
                mod = importlib.util.module_from_spec(spec)
                # dataclasses expects the module to be present in sys.modules
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                DslPyError = getattr(mod, "DslPyError")
                transpile = getattr(mod, "transpile")
            except Exception as ex:
                raise ValueError(f"dslpy support missing: {type(ex).__name__}: {ex}") from ex

            try:
                mldsl_src = transpile(text)  # type: ignore[misc]
            except Exception as ex:
                raise ValueError(f"dslpy transpile error: {ex}") from ex

            v = api.validate_source(mldsl_src)
            if not v.get("ok"):
                errs = "\n".join(v.get("errors") or [])
                raise ValueError(f"dslpy transpile produced invalid MLDSL:\n{errs}")

            # Keep temp MLDSL filename distinct from a user-visible main.mldsl
            # (important when the user allows either main.mldsl or main.dslpy).
            tmp_mldsl = (p.parent / (p.name + ".mldsl")).resolve()
            if session_dir not in tmp_mldsl.parents and tmp_mldsl != session_dir:
                raise ValueError("dslpy generated path escaped session dir (bug)")
            tmp_mldsl.write_text(mldsl_src, encoding="utf-8")
            created_files.add(tmp_mldsl)

            cmd = [sys.executable, str(REPO_ROOT / "tools" / "mldsl_compile.py"), str(tmp_mldsl), "--print-plan"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                plan = json.loads(proc.stdout or "{}")
                entries = plan.get("entries") if isinstance(plan, dict) else None
                empty_plan = isinstance(entries, list) and len(entries) == 0
            except Exception:
                empty_plan = None
            if proc.returncode != 0:
                raise ValueError(f"dslpy compile failed:\n{(proc.stderr or proc.stdout)[-4000:]}")
            if empty_plan is True:
                raise ValueError("dslpy transpile compiled but produced EMPTY plan (no entries)")

        # Guardrails: our DSL doesn't support these keywords (common hallucinations).
        lowered = text.lower()
        if "`" in lowered:
            raise ValueError("unsupported keyword in MLDSL: '`' (use braces {} only)")
        banned_patterns = [
            # Common hallucinated "structured" keywords. Our MLDSL uses only `{}` blocks.
            r"\bконец\b",
            r"\bиначе\b",
            r"\bтогда\b",
            r"\belif\b",
            r"\bendif\b",
            r"\bend\b",
            r"\bthen\b",
            # People (and models) often write empty событие()/действие() blocks.
            r"\bсобытие\(\s*\)",
            r"\bдействие\(\s*\)",
        ]
        for pat in banned_patterns:
            if re.search(pat, lowered):
                raise ValueError(f"unsupported keyword in MLDSL: {pat!r} (use braces {{}} only)")
        if "sessionrel" in (path or "").lower():
            raise ValueError("do not use literal 'sessionRel' in path; use the real sessionRel value from session_info()")
        if is_mldsl:
            lowered_src = (text or "").lower()
            if template_marker and template_marker.lower() not in lowered_src:
                raise ValueError(f"template marker missing: {template_marker}")
            if required_substrings and not any(s in lowered_src for s in required_substrings):
                raise ValueError(
                    "output does not contain required marker(s): " + ", ".join(sorted(required_substrings))
                )

            # Enforce banned actions if the request specified any.
            if banned_tokens:
                used = _extract_calls(text)
                used_resolved: set[str] = set()
                for mod_name, func_name in sorted(used):
                    r = api.resolve(mod_name, func_name)
                    if not r:
                        continue
                    spec = r.spec or {}
                    used_resolved.add(f"{r.module}.{r.canon}".lower())
                    for a in spec.get("aliases") or []:
                        if isinstance(a, str) and a:
                            used_resolved.add(a.strip().lower())
                if any(t in used_resolved for t in banned_tokens):
                    raise ValueError("request forbids using: " + ", ".join(sorted(banned_tokens)))

                if required_aliases and not any(a in used_resolved for a in required_aliases):
                    raise ValueError(
                        "output does not use required action(s): " + ", ".join(sorted(required_aliases))
                    )

            # Guardrail: before writing raw MLDSL in agent mode, require that the model looked up
            # signatures/docs for every API call it uses. This reduces "action confusion" errors
            # (e.g., using FillRegion instead of a Line algorithm).
            if not builder_mode:
                used = _extract_calls(text)
                missing: list[str] = []
                for mod_name, func_name in sorted(used):
                    r = api.resolve(mod_name, func_name)
                    if not r:
                        continue
                    # If the call existed in the starting template, don't require lookup again.
                    if template_base_used_resolved and f"{r.module}.{r.canon}".lower() in template_base_used_resolved:
                        continue
                    if (r.module, r.canon) not in looked_up:
                        missing.append(f"{r.module}.{r.canon}")
                if missing:
                    raise ValueError(
                        "before write_file, call get_sig/get_doc for: "
                        + ", ".join(missing[:25])
                        + (" ...(more)" if len(missing) > 25 else "")
                    )
            v = api.validate_source(text)
            if not v.get("ok"):
                import difflib

                errs = list(v.get("errors") or [])
                extra: list[str] = []
                for e in errs:
                    if isinstance(e, str) and e.startswith("unknown function: "):
                        mf = e.split("unknown function: ", 1)[1].strip()
                        if "." in mf:
                            mm, ff = mf.split(".", 1)
                            mm_n = norm_ident(mm)
                            mod_key = MODULE_ALIASES.get(mm_n, mm)
                            if mod_key not in api.api:
                                close_mods = difflib.get_close_matches(mod_key, api.list_modules(), n=3, cutoff=0.6)
                                if close_mods:
                                    extra.append(f"suggest: module `{mm}` -> {', '.join(close_mods)}")
                            else:
                                close = difflib.get_close_matches(ff, api.list_funcs(mod_key), n=5, cutoff=0.6)
                                if close:
                                    extra.append(f"suggest: {mm}.{ff} -> {mod_key}.{close[0]} (also: {', '.join(close[1:4])})")

                msg = "MLDSL validation failed:\n" + "\n".join(errs)
                if extra:
                    msg += "\n\n" + "\n".join(extra)
                msg += "\n\nTip: use search_api(\"...\") then get_sig(module, func) before writing."
                raise ValueError(msg)
        p.write_text(text, encoding="utf-8")
        created_files.add(p)
        # Auto-validate MLDSL files: compile and require non-empty plan.
        if p.suffix.lower() == ".mldsl":
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "mldsl_compile.py"), str(p), "--print-plan"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                plan = json.loads(proc.stdout or "{}")
                entries = plan.get("entries") if isinstance(plan, dict) else None
                empty_plan = isinstance(entries, list) and len(entries) == 0
            except Exception:
                empty_plan = None
            if proc.returncode != 0:
                raise ValueError(f"compile failed for {path}:\n{(proc.stderr or proc.stdout)[-4000:]}")
            if empty_plan is True:
                raise ValueError(
                    f"compile produced EMPTY plan for {path}. "
                    f"Make sure you have valid blocks like `событие(вход) {{ ... }}` or `event(join) {{ ... }}` "
                    f"and use only existing actions."
                )
        return f"OK: wrote {path} ({len(text or '')} chars)"

    # -------------------------
    # Builder-mode (tool-only AST builder)
    # -------------------------
    @dataclass
    class _BBlock:
        id: str
        kind: str
        header: str

    @dataclass
    class _BFile:
        id: str
        language: str
        out_path: str
        lines: list[str]
        stack: list[_BBlock]

    _builder_files: dict[str, _BFile] = {}
    _builder_next_id = 0

    def _bid(prefix: str) -> str:
        nonlocal _builder_next_id
        _builder_next_id += 1
        return f"{prefix}{_builder_next_id}"

    def _bfile(file_id: str) -> _BFile:
        f = _builder_files.get(file_id)
        if not f:
            raise ValueError(f"unknown file_id: {file_id}")
        return f

    def _quote_str(s: str) -> str:
        return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _emit_value(v) -> str:
        # raw MLDSL expression wrapper: {"expr": "item(...)"}
        if isinstance(v, dict) and "expr" in v:
            return str(v["expr"])
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if v is None:
            return "null"
        return _quote_str(str(v))

    def _indent_for(f: _BFile) -> str:
        return "    " * len(f.stack)

    def _start_block(f: _BFile, kind: str, header: str) -> str:
        block_id = _bid("b")
        f.lines.append(_indent_for(f) + header + " {")
        f.stack.append(_BBlock(id=block_id, kind=kind, header=header))
        return block_id

    def _end_block(f: _BFile, block_id: str, kind: str) -> str:
        if not f.stack:
            raise ValueError("no open blocks")
        top = f.stack[-1]
        if top.id != block_id or top.kind != kind:
            raise ValueError(f"end_{kind}: top is {top.kind}({top.id}), requested {kind}({block_id})")
        f.stack.pop()
        f.lines.append(_indent_for(f) + "}")
        return block_id

    def _end_top_block(f: _BFile, kind: str) -> str:
        if not f.stack:
            raise ValueError("no open blocks")
        top = f.stack[-1]
        if top.kind != kind:
            raise ValueError(f"end_{kind}: top is {top.kind}({top.id}), expected {kind}(...)")
        f.stack.pop()
        f.lines.append(_indent_for(f) + "}")
        return top.id

    def _render_builder_file(f: _BFile) -> str:
        if f.stack:
            open_list = ", ".join(f"{b.kind}({b.id})" for b in f.stack)
            raise ValueError(f"unclosed blocks: {open_list}")
        return "\n".join(f.lines).rstrip() + "\n"

    def _builder_validate_cond(cond: str) -> None:
        # Our MLDSL `if` doesn't support ==/!=; enforce early so models learn.
        c = (cond or "").strip()
        if "==" in c or "!=" in c:
            raise ValueError("if condition must use only <, <=, >, >= (no == or !=). Use and_(x>=N, x<=N) style.")

    if builder_mode or ir_mode:
        @tool
        def new_program(path: str | None = None, file_path: str | None = None, language: str = "mldsl") -> str:
            """Create a new program in the current session. Returns JSON {file_id, path, language}.
            language: 'mldsl' only for now.
            """
            lang = (language or "").strip().lower()
            if lang not in {"mldsl"}:
                raise ValueError("builder supports only language='mldsl' for now")
            out_path = (path or file_path or "").strip()
            if not out_path:
                if len(requested_groups) == 1:
                    out_path = sorted(list(requested_groups[0]))[0]
                else:
                    out_path = "main.mldsl"
            # enforce requested filenames if any
            if requested_suffixes:
                normp = out_path.replace("\\", "/")
                if not any(normp.endswith(suf) for suf in requested_suffixes):
                    raise ValueError("path must match requested file(s): " + ", ".join(sorted(requested_suffixes)))
            # If the model repeats new_program for the same path, reuse the existing file_id.
            for fid, bf in _builder_files.items():
                if bf.out_path == out_path and bf.language == lang:
                    return json.dumps(
                        {
                            "file_id": fid,
                            "path": out_path,
                            "language": lang,
                            "reused": True,
                            "note": "Program already created. STOP calling new_program/create_file. Next: list_modules -> list_funcs -> get_sig -> begin_event/add_action -> finalize_program.",
                        },
                        ensure_ascii=False,
                    )
            file_id = _bid("f")
            _builder_files[file_id] = _BFile(id=file_id, language=lang, out_path=out_path, lines=[], stack=[])
            return json.dumps({"file_id": file_id, "path": out_path, "language": lang}, ensure_ascii=False)

        # Friendly aliases (models often prefer these names).
        @tool
        def create_file(path: str | None = None, file_path: str | None = None, language: str = "mldsl") -> str:
            """Alias for new_program()."""
            lang = (language or "").strip().lower()
            if lang not in {"mldsl"}:
                raise ValueError("builder supports only language='mldsl' for now")
            out_path = (path or file_path or "").strip()
            if not out_path:
                if len(requested_groups) == 1:
                    out_path = sorted(list(requested_groups[0]))[0]
                else:
                    out_path = "main.mldsl"
            if requested_suffixes:
                normp = out_path.replace("\\", "/")
                if not any(normp.endswith(suf) for suf in requested_suffixes):
                    raise ValueError("path must match requested file(s): " + ", ".join(sorted(requested_suffixes)))
            for fid, bf in _builder_files.items():
                if bf.out_path == out_path and bf.language == lang:
                    return json.dumps(
                        {
                            "file_id": fid,
                            "path": out_path,
                            "language": lang,
                            "reused": True,
                            "note": "Program already created. STOP calling new_program/create_file. Next: list_modules -> list_funcs -> get_sig -> begin_event/add_action -> finalize_program.",
                        },
                        ensure_ascii=False,
                    )
            file_id = _bid("f")
            _builder_files[file_id] = _BFile(id=file_id, language=lang, out_path=out_path, lines=[], stack=[])
            return json.dumps({"file_id": file_id, "path": out_path, "language": lang}, ensure_ascii=False)

        @tool
        def create_program(path: str | None = None, file_path: str | None = None, language: str = "mldsl") -> str:
            """Alias for new_program()."""
            lang = (language or "").strip().lower()
            if lang not in {"mldsl"}:
                raise ValueError("builder supports only language='mldsl' for now")
            out_path = (path or file_path or "").strip()
            if not out_path:
                if len(requested_groups) == 1:
                    out_path = sorted(list(requested_groups[0]))[0]
                else:
                    out_path = "main.mldsl"
            if requested_suffixes:
                normp = out_path.replace("\\", "/")
                if not any(normp.endswith(suf) for suf in requested_suffixes):
                    raise ValueError("path must match requested file(s): " + ", ".join(sorted(requested_suffixes)))
            for fid, bf in _builder_files.items():
                if bf.out_path == out_path and bf.language == lang:
                    return json.dumps(
                        {
                            "file_id": fid,
                            "path": out_path,
                            "language": lang,
                            "reused": True,
                            "note": "Program already created. STOP calling new_program/create_file. Next: list_modules -> list_funcs -> get_sig -> begin_event/add_action -> finalize_program.",
                        },
                        ensure_ascii=False,
                    )
            file_id = _bid("f")
            _builder_files[file_id] = _BFile(id=file_id, language=lang, out_path=out_path, lines=[], stack=[])
            return json.dumps({"file_id": file_id, "path": out_path, "language": lang}, ensure_ascii=False)

        @tool
        def begin_event(file_id: str, name: str | None = None, event_name: str | None = None) -> str:
            """Open an event block. Returns JSON {event_id}."""
            f = _bfile(file_id)
            nm = (name or event_name or builder_ctx.get("event_name") or "").strip()
            if not nm:
                raise ValueError("name is required")
            ev_id = _start_block(f, "event", f"event({_quote_str(nm)})")
            return json.dumps({"event_id": ev_id}, ensure_ascii=False)

        @tool
        def end_event(file_id: str, event_id: str | None = None, block_id: str | None = None) -> str:
            """Close an event block. If event_id omitted, closes the top open event."""
            f = _bfile(file_id)
            bid = (event_id or block_id or builder_ctx.get("event_id") or "").strip()
            if not bid:
                closed = _end_top_block(f, "event")
                return json.dumps({"event_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "event")
            return json.dumps({"event_id": bid}, ensure_ascii=False)

        @tool
        def start_event(file_id: str, name: str | None = None, event_name: str | None = None) -> str:
            """Alias for begin_event()."""
            f = _bfile(file_id)
            nm = (name or event_name or builder_ctx.get("event_name") or "").strip()
            if not nm:
                raise ValueError("name is required")
            ev_id = _start_block(f, "event", f"event({_quote_str(nm)})")
            return json.dumps({"event_id": ev_id}, ensure_ascii=False)

        @tool
        def close_event(file_id: str, event_id: str | None = None, block_id: str | None = None) -> str:
            """Alias for end_event(). If event_id omitted, closes the top open event."""
            f = _bfile(file_id)
            bid = (event_id or block_id or builder_ctx.get("event_id") or "").strip()
            if not bid:
                closed = _end_top_block(f, "event")
                return json.dumps({"event_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "event")
            return json.dumps({"event_id": bid}, ensure_ascii=False)

        @tool
        def begin_loop(
            file_id: str,
            name: str | None = None,
            loop_name: str | None = None,
            every_ticks: int | None = None,
            every: int | None = None,
        ) -> str:
            """Open a loop block. Returns JSON {loop_id}. Example: loop("timer", 20) { ... }"""
            f = _bfile(file_id)
            nm = (name or loop_name or "").strip()
            if not nm:
                raise ValueError("name is required")
            tick = every_ticks if every_ticks is not None else every
            if tick is None:
                raise ValueError("every_ticks is required")
            if int(tick) <= 0:
                raise ValueError("every_ticks must be > 0")
            loop_id = _start_block(f, "loop", f"loop({_quote_str(nm)}, {int(tick)})")
            return json.dumps({"loop_id": loop_id}, ensure_ascii=False)

        @tool
        def end_loop(file_id: str, loop_id: str | None = None, block_id: str | None = None) -> str:
            """Close a loop block. If loop_id omitted, closes the top open loop."""
            f = _bfile(file_id)
            bid = (loop_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "loop")
                return json.dumps({"loop_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "loop")
            return json.dumps({"loop_id": bid}, ensure_ascii=False)

        @tool
        def start_loop(
            file_id: str,
            name: str | None = None,
            loop_name: str | None = None,
            every_ticks: int | None = None,
            every: int | None = None,
        ) -> str:
            """Alias for begin_loop()."""
            f = _bfile(file_id)
            nm = (name or loop_name or "").strip()
            if not nm:
                raise ValueError("name is required")
            tick = every_ticks if every_ticks is not None else every
            if tick is None:
                raise ValueError("every_ticks is required")
            if int(tick) <= 0:
                raise ValueError("every_ticks must be > 0")
            loop_id = _start_block(f, "loop", f"loop({_quote_str(nm)}, {int(tick)})")
            return json.dumps({"loop_id": loop_id}, ensure_ascii=False)

        @tool
        def close_loop(file_id: str, loop_id: str | None = None, block_id: str | None = None) -> str:
            """Alias for end_loop(). If loop_id omitted, closes the top open loop."""
            f = _bfile(file_id)
            bid = (loop_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "loop")
                return json.dumps({"loop_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "loop")
            return json.dumps({"loop_id": bid}, ensure_ascii=False)

        @tool
        def begin_if(file_id: str, condition: str | None = None, expr: str | None = None) -> str:
            """Open an if block. condition is MLDSL condition string (use only <,<=,>,>=). Returns JSON {if_id}."""
            f = _bfile(file_id)
            cond = (condition or expr or "").strip()
            if not cond:
                raise ValueError("condition is required")
            _builder_validate_cond(cond)
            if_id = _start_block(f, "if", f"if {cond}")
            return json.dumps({"if_id": if_id}, ensure_ascii=False)

        @tool
        def end_if(file_id: str, if_id: str | None = None, block_id: str | None = None) -> str:
            """Close an if block. If if_id omitted, closes the top open if."""
            f = _bfile(file_id)
            bid = (if_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "if")
                return json.dumps({"if_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "if")
            return json.dumps({"if_id": bid}, ensure_ascii=False)

        @tool
        def start_if(file_id: str, condition: str | None = None, expr: str | None = None) -> str:
            """Alias for begin_if()."""
            f = _bfile(file_id)
            cond = (condition or expr or "").strip()
            if not cond:
                raise ValueError("condition is required")
            _builder_validate_cond(cond)
            if_id = _start_block(f, "if", f"if {cond}")
            return json.dumps({"if_id": if_id}, ensure_ascii=False)

        @tool
        def close_if(file_id: str, if_id: str | None = None, block_id: str | None = None) -> str:
            """Alias for end_if(). If if_id omitted, closes the top open if."""
            f = _bfile(file_id)
            bid = (if_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "if")
                return json.dumps({"if_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "if")
            return json.dumps({"if_id": bid}, ensure_ascii=False)

        @tool
        def begin_call_block(
            file_id: str,
            target: str | None = None,
            call: str | None = None,
            module: str | None = None,
            func: str | None = None,
            parameters: dict | None = None,
            params: dict | None = None,
        ) -> str:
            """Open a call-style block like: if_player.имеет_право(...) { ... }.
            target: "module.func" (aliases allowed). parameters: dict of kw args; values may be literals or {expr:"raw"}.
            Returns JSON {ok,module,func,call_id}.
            """
            f = _bfile(file_id)
            tgt = (target or call or "").strip()
            if (not tgt) and module and func:
                tgt = f"{module}.{func}"
            if "." not in tgt:
                raise ValueError("target must be module.func")
            mod_raw, fn_raw = tgt.split(".", 1)
            r = api.resolve(mod_raw, fn_raw)
            if not r:
                raise ValueError(f"unknown function: {mod_raw}.{fn_raw}")

            spec = r.spec or {}
            spec_aliases = {a for a in (spec.get("aliases") or []) if isinstance(a, str)}
            call_params = [p for p in (spec.get("params") or []) if isinstance(p, dict) and p.get("name")]
            enums = [e for e in (spec.get("enums") or []) if isinstance(e, dict) and e.get("name")]
            allowed = {str(p["name"]) for p in call_params} | {str(e["name"]) for e in enums}
            provided = (parameters or params or {}) if (parameters or params) else {}
            if not isinstance(provided, dict):
                raise ValueError("parameters must be an object/dict")
            for k in provided.keys():
                if allowed and k not in allowed:
                    raise ValueError(f"{r.module}.{r.canon}: unknown kw arg `{k}` (allowed: {', '.join(sorted(allowed))})")
            # enum strict check when value is a plain string literal
            for e in enums:
                en = str(e["name"])
                if en not in provided:
                    continue
                v = provided[en]
                if isinstance(v, dict) and "expr" in v:
                    continue
                if isinstance(v, str):
                    opts = e.get("options")
                    if isinstance(opts, dict) and opts and v not in opts:
                        examples = ", ".join(list(opts.keys())[:10])
                        raise ValueError(f"enum `{en}`: неизвестное значение `{v}`. Варианты: {examples}")

            arg_parts: list[str] = []
            for p in call_params:
                n = str(p["name"])
                if n in provided:
                    arg_parts.append(f"{n}={_emit_value(provided[n])}")
            for e in enums:
                n = str(e["name"])
                if n in provided:
                    arg_parts.append(f"{n}={_emit_value(provided[n])}")

            emit_func = fn_raw.strip()
            if emit_func not in spec_aliases:
                emit_func = ""
            if not emit_func:
                for a in sorted(spec_aliases, key=len):
                    if not re.match(r"^[a-z][a-z0-9_]*$", a):
                        continue
                    if a.startswith(("unnamed", "gen_")):
                        continue
                    emit_func = a
                    break
            if not emit_func:
                emit_func = r.canon

            header = f"{r.module}.{emit_func}({', '.join(arg_parts)})"
            call_id = _start_block(f, "call", header)
            return json.dumps({"ok": True, "module": r.module, "func": r.canon, "call_id": call_id}, ensure_ascii=False)

        @tool
        def end_call_block(file_id: str, call_id: str | None = None, block_id: str | None = None) -> str:
            """Close a call block. If call_id omitted, closes the top open call."""
            f = _bfile(file_id)
            bid = (call_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "call")
                return json.dumps({"call_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "call")
            return json.dumps({"call_id": bid}, ensure_ascii=False)

        @tool
        def begin_select(file_id: str, selector: str | None = None, name: str | None = None) -> str:
            """Open a select block: select.<selector> { ... }. Returns JSON {select_id}."""
            f = _bfile(file_id)
            sel = (selector or name or "").strip()
            if not sel:
                raise ValueError("selector is required (e.g. allplayers)")
            select_id = _start_block(f, "select", f"select.{sel}")
            return json.dumps({"select_id": select_id}, ensure_ascii=False)

        @tool
        def end_select(file_id: str, select_id: str | None = None, block_id: str | None = None) -> str:
            """Close a select block. If select_id omitted, closes the top open select."""
            f = _bfile(file_id)
            bid = (select_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "select")
                return json.dumps({"select_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "select")
            return json.dumps({"select_id": bid}, ensure_ascii=False)

        @tool
        def start_select(file_id: str, selector: str | None = None, name: str | None = None) -> str:
            """Alias for begin_select()."""
            f = _bfile(file_id)
            sel = (selector or name or "").strip()
            if not sel:
                raise ValueError("selector is required (e.g. allplayers)")
            select_id = _start_block(f, "select", f"select.{sel}")
            return json.dumps({"select_id": select_id}, ensure_ascii=False)

        @tool
        def close_select(file_id: str, select_id: str | None = None, block_id: str | None = None) -> str:
            """Alias for end_select(). If select_id omitted, closes the top open select."""
            f = _bfile(file_id)
            bid = (select_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "select")
                return json.dumps({"select_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "select")
            return json.dumps({"select_id": bid}, ensure_ascii=False)

        @tool
        def begin_function(file_id: str, name: str | None = None, function_name: str | None = None) -> str:
            """Open a function block. Returns JSON {function_id}. Example: func(hello) { ... }"""
            f = _bfile(file_id)
            nm = (name or function_name or "").strip()
            if not nm:
                raise ValueError("name is required")
            fn_id = _start_block(f, "func", f"func({_quote_str(nm)})")
            return json.dumps({"function_id": fn_id}, ensure_ascii=False)

        @tool
        def end_function(file_id: str, function_id: str | None = None, block_id: str | None = None) -> str:
            """Close a function block. If function_id omitted, closes the top open func."""
            f = _bfile(file_id)
            bid = (function_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "func")
                return json.dumps({"function_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "func")
            return json.dumps({"function_id": bid}, ensure_ascii=False)

        @tool
        def start_function(file_id: str, name: str | None = None, function_name: str | None = None) -> str:
            """Alias for begin_function()."""
            f = _bfile(file_id)
            nm = (name or function_name or "").strip()
            if not nm:
                raise ValueError("name is required")
            fn_id = _start_block(f, "func", f"func({_quote_str(nm)})")
            return json.dumps({"function_id": fn_id}, ensure_ascii=False)

        @tool
        def close_function(file_id: str, function_id: str | None = None, block_id: str | None = None) -> str:
            """Alias for end_function(). If function_id omitted, closes the top open func."""
            f = _bfile(file_id)
            bid = (function_id or block_id or "").strip()
            if not bid:
                closed = _end_top_block(f, "func")
                return json.dumps({"function_id": closed, "auto": True}, ensure_ascii=False)
            _end_block(f, bid, "func")
            return json.dumps({"function_id": bid}, ensure_ascii=False)

        @tool
        def set_var(file_id: str, name: str, expr) -> str:
            """Emit an assignment: name = expr. expr can be a number/bool/string or {expr: 'raw_mldsl'}."""
            f = _bfile(file_id)
            var = (name or "").strip()
            if not var:
                raise ValueError("name is required")
            f.lines.append(_indent_for(f) + f"{var} = {_emit_value(expr)}")
            return json.dumps({"ok": True}, ensure_ascii=False)

        @tool
        def assign(file_id: str, name: str, expr) -> str:
            """Alias for set_var()."""
            f = _bfile(file_id)
            var = (name or "").strip()
            if not var:
                raise ValueError("name is required")
            f.lines.append(_indent_for(f) + f"{var} = {_emit_value(expr)}")
            return json.dumps({"ok": True}, ensure_ascii=False)

        @tool
        def set_variable(file_id: str, name: str, expr) -> str:
            """Alias for set_var()."""
            f = _bfile(file_id)
            var = (name or "").strip()
            if not var:
                raise ValueError("name is required")
            f.lines.append(_indent_for(f) + f"{var} = {_emit_value(expr)}")
            return json.dumps({"ok": True}, ensure_ascii=False)

        @tool
        def add_action(
            file_id: str,
            target: str | None = None,
            action: str | None = None,
            module: str | None = None,
            func: str | None = None,
            parameters: dict | None = None,
            params: dict | None = None,
        ) -> str:
            """Add an action call like player.message(...).
            target: "module.func" (aliases allowed). args: dict of kw args; values may be literals or {expr:"raw"}.
            Returns JSON {ok,module,func}.
            """
            f = _bfile(file_id)
            tgt = (target or action or "").strip()
            if (not tgt) and module and func:
                tgt = f"{module}.{func}"
            if "." not in tgt:
                raise ValueError("target must be module.func")
            mod_raw, fn_raw = tgt.split(".", 1)
            r = api.resolve(mod_raw, fn_raw)
            if not r:
                raise ValueError(f"unknown function: {mod_raw}.{fn_raw}")

            spec = r.spec or {}
            spec_aliases = {a for a in (spec.get("aliases") or []) if isinstance(a, str)}
            params = [p for p in (spec.get("params") or []) if isinstance(p, dict) and p.get("name")]
            enums = [e for e in (spec.get("enums") or []) if isinstance(e, dict) and e.get("name")]
            allowed = {str(p["name"]) for p in params} | {str(e["name"]) for e in enums}
            provided = (parameters or params or {}) if (parameters or params) else {}
            if not isinstance(provided, dict):
                raise ValueError("parameters must be an object/dict")
            for k in provided.keys():
                if allowed and k not in allowed:
                    raise ValueError(f"{r.module}.{r.canon}: unknown kw arg `{k}` (allowed: {', '.join(sorted(allowed))})")
            # enum strict check when value is a plain string literal
            for e in enums:
                en = str(e["name"])
                if en not in provided:
                    continue
                v = provided[en]
                if isinstance(v, dict) and "expr" in v:
                    continue
                if isinstance(v, str):
                    opts = e.get("options")
                    if isinstance(opts, dict) and opts and v not in opts:
                        examples = ", ".join(list(opts.keys())[:10])
                        raise ValueError(f"enum `{en}`: неизвестное значение `{v}`. Варианты: {examples}")

            # Deterministic arg order: params then enums, only if provided.
            arg_parts: list[str] = []
            for p in params:
                n = str(p["name"])
                if n in provided:
                    arg_parts.append(f"{n}={_emit_value(provided[n])}")
            for e in enums:
                n = str(e["name"])
                if n in provided:
                    arg_parts.append(f"{n}={_emit_value(provided[n])}")

            # Prefer emitting a readable alias (instead of "unnamed_N") when possible:
            # - keep the originally requested alias if it exists
            # - otherwise pick the first ASCII snake_case alias that isn't "unnamed_*"/"gen_*"
            emit_func = fn_raw.strip()
            if emit_func not in spec_aliases:
                emit_func = ""
            if not emit_func:
                for a in sorted(spec_aliases, key=len):
                    if not re.match(r"^[a-z][a-z0-9_]*$", a):
                        continue
                    if a.startswith(("unnamed", "gen_")):
                        continue
                    emit_func = a
                    break
            if not emit_func:
                emit_func = r.canon

            f.lines.append(_indent_for(f) + f"{r.module}.{emit_func}({', '.join(arg_parts)})")
            return json.dumps({"ok": True, "module": r.module, "func": r.canon}, ensure_ascii=False)

        @tool
        def preview_program(file_id: str) -> str:
            """Return current generated MLDSL (fails if blocks are unclosed)."""
            f = _bfile(file_id)
            return _render_builder_file(f)

        @tool
        def render_program(file_id: str) -> str:
            """Alias for preview_program()."""
            f = _bfile(file_id)
            return _render_builder_file(f)

        @tool
        def finalize_program(file_id: str) -> str:
            """Write the program file and compile it (must produce non-empty plan). Returns JSON {path, ok}."""
            f = _bfile(file_id)
            src = _render_builder_file(f)
            # Use internal writer (compiles & validates).
            _write_file_impl(f.out_path, src)
            return json.dumps({"ok": True, "path": f.out_path}, ensure_ascii=False)

        @tool
        def save_program(file_id: str) -> str:
            """Alias for finalize_program()."""
            f = _bfile(file_id)
            src = _render_builder_file(f)
            _write_file_impl(f.out_path, src)
            return json.dumps({"ok": True, "path": f.out_path}, ensure_ascii=False)

        tools = [
            session_info,
            list_modules,
            search_api,
            create_tasks,
            list_tasks,
            update_task,
            list_funcs,
            list_functions,
            list_files,
            resolve_target,
            dump_module,
            get_sig,
            get_doc,
            validate_mldsl,
            log_thought,
            enter_synthesis,
            exit_synthesis,
            check_compilation,
            new_program,
            create_file,
            create_program,
            begin_event,
            end_event,
            start_event,
            close_event,
            begin_loop,
            end_loop,
            start_loop,
            close_loop,
            begin_if,
            end_if,
            start_if,
            close_if,
            begin_call_block,
            end_call_block,
            begin_select,
            end_select,
            start_select,
            close_select,
            begin_function,
            end_function,
            start_function,
            close_function,
            set_var,
            assign,
            set_variable,
            add_action,
            preview_program,
            render_program,
            finalize_program,
            save_program,
        ]
    else:
        tools = [
            session_info,
            list_modules,
            search_api,
            create_tasks,
            list_tasks,
            update_task,
            list_funcs,
            list_functions,
            list_files,
            list_templates,
            get_template,
            resolve_target,
            dump_module,
            get_doc,
            get_sig,
            validate_mldsl,
            log_thought,
            enter_synthesis,
            exit_synthesis,
            check_compilation,
            read_file,
        ]

    # Builder-mode helper: substitute placeholder ids like "<file_id>" using last seen ids.
    builder_ctx: dict[str, str] = {}
    if builder_mode or ir_mode:
        # Opportunistic hints extracted from the user request for weaker local models.
        # Example request: "событие Вход игрока, внутри ..."
        m = re.search(r"(?:\bсобытие\b|\bevent\b)\s+([^\n,]+)", request, re.I)
        if m:
            nm = (m.group(1) or "").strip().strip('"').strip("'")
            if nm:
                builder_ctx["event_name"] = nm

    def _builder_ctx_apply(obj):
        if not builder_mode:
            return obj
        if isinstance(obj, list):
            return [_builder_ctx_apply(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _builder_ctx_apply(v) for k, v in obj.items()}
        if isinstance(obj, str):
            s = obj.strip()
            # Common placeholder formats:
            # - "<file_id>"
            # - "<result of new_program.file_id>"
            if s.startswith("<") and s.endswith(">") and len(s) > 2:
                key = s[1:-1].strip()
                # direct match
                if key in builder_ctx:
                    return builder_ctx[key]
                low = key.lower()
                # "<result of new_program.file_id>" style
                if "file_id" in low and ("new_program" in low or "create_file" in low or "create_program" in low):
                    if "file_id" in builder_ctx:
                        return builder_ctx["file_id"]
                # Some models incorrectly reference begin_event.file_id; treat it as the current file_id.
                if "file_id" in low and ("begin_event" in low or "start_event" in low):
                    if "file_id" in builder_ctx:
                        return builder_ctx["file_id"]
                if "event_id" in low and ("begin_event" in low or "start_event" in low):
                    if "event_id" in builder_ctx:
                        return builder_ctx["event_id"]
                if "if_id" in low and ("begin_if" in low or "start_if" in low):
                    if "if_id" in builder_ctx:
                        return builder_ctx["if_id"]
                if "loop_id" in low and ("begin_loop" in low or "start_loop" in low):
                    if "loop_id" in builder_ctx:
                        return builder_ctx["loop_id"]
                if "select_id" in low and ("begin_select" in low or "start_select" in low):
                    if "select_id" in builder_ctx:
                        return builder_ctx["select_id"]
                if "function_id" in low and ("begin_function" in low or "start_function" in low):
                    if "function_id" in builder_ctx:
                        return builder_ctx["function_id"]
                if "call_id" in low and ("begin_call_block" in low or "start_call_block" in low or "begin_call" in low):
                    if "call_id" in builder_ctx:
                        return builder_ctx["call_id"]
        return obj

    def _builder_ctx_capture(res: str) -> None:
        if not builder_mode or not isinstance(res, str):
            return
        try:
            obj = json.loads(res)
        except Exception:
            return
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if not isinstance(v, str):
                continue
            # accept common id keys
            if k in {"file_id", "event_id", "if_id", "loop_id", "select_id", "function_id", "block_id", "id"}:
                builder_ctx[k] = v
            elif k.endswith("_id"):
                builder_ctx[k] = v

    def _builder_fix_file_id(name: str, args: dict) -> dict:
        if not builder_mode or not isinstance(args, dict):
            return args
        # Some models mistakenly put a filepath into file_id.
        fid = args.get("file_id")
        if isinstance(fid, str) and (fid.endswith(".mldsl") or "/" in fid or "\\" in fid):
            if "file_id" in builder_ctx:
                args["file_id"] = builder_ctx["file_id"]
        # Some models put a numeric "1"/"0" or similar instead of "f1".
        if isinstance(fid, str) and fid.strip().isdigit():
            if "file_id" in builder_ctx:
                args["file_id"] = builder_ctx["file_id"]
        # Some models put a block id ("b1") into file_id.
        if isinstance(fid, str) and fid.startswith("b") and "file_id" in builder_ctx:
            args["file_id"] = builder_ctx["file_id"]
        # Some models omit file_id for finalize; use last file_id if we have it.
        if name in {"finalize_program", "save_program"} and not args.get("file_id") and "file_id" in builder_ctx:
            args["file_id"] = builder_ctx["file_id"]
        return args

    def _builder_fix_block_ids(name: str, args: dict) -> dict:
        if not builder_mode or not isinstance(args, dict):
            return args
        if name in {"end_event", "close_event"}:
            eid = args.get("event_id") or args.get("block_id")
            # Some models put the event *name* here. Prefer the actual last event_id.
            if isinstance(eid, str):
                if eid and not eid.startswith("b") and "event_id" in builder_ctx:
                    args["event_id"] = builder_ctx["event_id"]
        if name in {"end_if", "close_if"}:
            iid = args.get("if_id") or args.get("block_id")
            if isinstance(iid, str):
                if iid and not iid.startswith("b") and "if_id" in builder_ctx:
                    args["if_id"] = builder_ctx["if_id"]
        if name in {"end_loop", "close_loop"}:
            lid = args.get("loop_id") or args.get("block_id")
            if isinstance(lid, str):
                if lid and not lid.startswith("b") and "loop_id" in builder_ctx:
                    args["loop_id"] = builder_ctx["loop_id"]
        if name in {"end_select", "close_select"}:
            sid = args.get("select_id") or args.get("block_id")
            if isinstance(sid, str):
                if sid and not sid.startswith("b") and "select_id" in builder_ctx:
                    args["select_id"] = builder_ctx["select_id"]
        if name in {"end_function", "close_function"}:
            fid = args.get("function_id") or args.get("block_id")
            if isinstance(fid, str):
                if fid and not fid.startswith("b") and "function_id" in builder_ctx:
                    args["function_id"] = builder_ctx["function_id"]
        if name in {"end_call_block"}:
            cid = args.get("call_id") or args.get("block_id")
            if isinstance(cid, str):
                if cid and not cid.startswith("b") and "call_id" in builder_ctx:
                    args["call_id"] = builder_ctx["call_id"]
        return args

    if (not builder_mode) and allow_write:
        @tool
        def write_file(path: str, content: str) -> str:
            "Write a UTF-8 text file under repo root (creates parent dirs)."
            return _write_file_impl(path, content)

        tools.append(write_file)

    def parse_tool_calls_from_content(text: str) -> list[dict]:
        # Fallback for models that emit tool calls in markdown/xml blocks instead of native tool_calls.
        # Examples:
        # ```tool_call
        # {"name": "list_modules", "parameters": {}}
        # ```
        #
        # <tool_call>
        # {"name": "tool_name", "arguments": {"x": 1}}
        # </tool_call>
        if not text:
            return []
        calls = []

        def _args_from(obj: dict) -> dict:
            args = obj.get("args") or obj.get("parameters") or obj.get("arguments")
            if isinstance(args, dict):
                return args
            # Some models omit "arguments" and put params at top-level:
            # {"name":"search_api","query":"x","limit":10}
            return {k: v for k, v in obj.items() if k not in {"name", "id", "tool", "tool_name"}}

        # 0) If the model emitted a bare JSON object like: {"name": "...", "arguments": {...}}
        s = text.strip()
        if s.startswith("{") and ("\"name\"" in s or "'name'" in s):
            try:
                obj = json.loads(s)
                name = obj.get("name")
                args = _args_from(obj)
                if isinstance(name, str) and name.lower() == "create_file" and (not builder_mode):
                    name = "write_file"
                if name:
                    return [{"id": "bare_1", "name": name, "args": args}]
            except Exception:
                pass

        # 1) If it's in a ```json ... ``` fence, parse *all* such blocks.
        #    Many local models output a sequence of tool calls as multiple ```json fences.
        if "```json" in text.lower():
            for m in re.finditer(r"```json\s*(.*?)\s*```", text, re.S | re.I):
                blob = (m.group(1) or "").strip()
                if not blob:
                    continue
                try:
                    obj = json.loads(blob)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                name = obj.get("name")
                args = _args_from(obj)
                if isinstance(name, str) and name.lower() == "create_file" and (not builder_mode):
                    name = "write_file"
                if name:
                    calls.append({"id": f"jsonfence_{len(calls)+1}", "name": name, "args": args})
            if calls:
                return calls

        # 2) Some local models dump multiple bare JSON objects (not wrapped in <tool_call> or ``` fences).
        #    Example:
        #    { "name": "new_program", "arguments": {...} }
        #    { "name": "begin_event", "arguments": {...} }
        if "\"name\"" in text and "{" in text and "}" in text:
            i = 0
            n = len(text)
            while i < n:
                j = text.find("{", i)
                if j < 0:
                    break
                depth = 0
                in_str = False
                esc = False
                end = -1
                for k in range(j, n):
                    ch = text[k]
                    if esc:
                        esc = False
                        continue
                    if ch == "\\":
                        esc = True
                        continue
                    if ch == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = k + 1
                            break
                if end == -1:
                    break
                blob = text[j:end].strip()
                i = end
                try:
                    obj = json.loads(blob)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                name = obj.get("name")
                args = _args_from(obj)
                if isinstance(name, str) and name.lower() == "create_file" and (not builder_mode):
                    name = "write_file"
                if name:
                    calls.append({"id": f"bare_{len(calls)+1}", "name": name, "args": args})
            if calls:
                return calls
        patterns = [
            r"```tool_call\s*(\{.*?\})\s*```",
            r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
            r"<tool_calls>\s*(\{.*?\})\s*</tool_calls>",
            r"<tool_code>\s*(\{.*?\})\s*</tool_code>",
            # tolerate missing closing tag
            r"<tool_call>\s*(\{.*?\})(?:\s*</tool_call>)?",
            r"<tool_calls>\s*(\{.*?\})(?:\s*</tool_calls>)?",
            r"<tool_code>\s*(\{.*?\})(?:\s*</tool_code>)?",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.S):
                blob = m.group(1).strip()
                try:
                    obj = json.loads(blob)
                except Exception:
                    continue
                name = obj.get("name")
                args = _args_from(obj)
                if isinstance(name, str) and name.lower() == "create_file" and (not builder_mode):
                    name = "write_file"
                if name:
                    calls.append({"id": f"fallback_{len(calls)+1}", "name": name, "args": args})

        # Robust fallback: scan for <tool_call> and parse the first JSON object that follows.
        if not calls and ("<tool_call" in text or "<tool_calls" in text or "<tool_code" in text):
            def extract_json_from(i: int) -> str | None:
                j = text.find("{", i)
                if j < 0:
                    return None
                depth = 0
                in_str = False
                esc = False
                for k in range(j, len(text)):
                    ch = text[k]
                    if esc:
                        esc = False
                        continue
                    if ch == "\\":
                        esc = True
                        continue
                    if ch == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return text[j : k + 1]
                return None

            idx = 0
            while True:
                idx_call = text.find("<tool_call", idx)
                idx_code = text.find("<tool_code", idx)
                if idx_call < 0 and idx_code < 0:
                    break
                if idx_call < 0:
                    idx = idx_code
                elif idx_code < 0:
                    idx = idx_call
                else:
                    idx = min(idx_call, idx_code)
                if idx < 0:
                    break
                blob = extract_json_from(idx)
                idx = idx + 9
                if not blob:
                    continue
                try:
                    obj = json.loads(blob)
                except Exception:
                    continue
                name = obj.get("name")
                args = _args_from(obj)
                if name:
                    calls.append({"id": f"fallback_{len(calls)+1}", "name": name, "args": args})
        return calls

    def exec_tool_call(tc: dict) -> str:
        name = tc.get("name")
        args = tc.get("args") or {}
        # Some models follow a "tool_name" wrapper: {"name":"tool_name","arguments":{"name":"list_modules",...}}
        if name == "tool_name" and isinstance(args, dict) and "name" in args:
            name = args.get("name")
            args = args.get("arguments") or args.get("args") or {}
        # Tolerate "either/or" names like "new_program/create_file".
        if isinstance(name, str) and "/" in name:
            parts = [p.strip() for p in name.split("/") if p.strip()]
            for p in parts:
                if any(getattr(t, "name", None) == p for t in tools):
                    name = p
                    break
        # Common arg-name normalizations for builder tools.
        if builder_mode and isinstance(args, dict) and isinstance(name, str):
            if name == "add_action" and "args" in args and "parameters" not in args:
                args["parameters"] = args.pop("args")
        # Substitute placeholders like "<file_id>".
        args = _builder_ctx_apply(args)
        args = _builder_fix_file_id(str(name or ""), args)
        args = _builder_fix_block_ids(str(name or ""), args)
        tool_fn = next((t for t in tools if getattr(t, "name", None) == name), None)
        if not tool_fn:
            return f"ERROR: unknown tool {name}"
        try:
            res = str(tool_fn.invoke(args))
            _builder_ctx_capture(res)
            return res
        except Exception as ex:
            return f"ERROR: {type(ex).__name__}: {ex}"

    # ---- agent loop ----
    system_native = (
        "Ты ИИ-кодер для MLDSL (русский язык).\n"
        "У тебя есть tool-calling. Используй инструменты, чтобы:\n"
        "- посмотреть список модулей/функций\n"
        "- получить документацию по функции\n"
        "- проверить компиляцию .mldsl\n"
        f"- записывать файлы: {'ДА' if allow_write else 'НЕТ'}\n\n"
        "Правила:\n"
        "- НЕ выдумывай несуществующие функции.\n"
        "- Перед генерацией кода подтяни docs по тем функциям, которые будешь использовать.\n"
        "- СИНТАКСИС: только блоки с фигурными скобками `{}` и по 1 выражению на строку.\n"
        "- НЕТ ключевых слов `конец`, `иначе`, `then`, `endif`.\n"
        "- Всегда указывай имя события: `событие(вход) { ... }` или `event(join) { ... }`.\n"
        "- Если пишешь файл, обязательно потом сделай check_compilation для него.\n"
        "- Пиши MLDSL максимально просто для новичков (используй алиасы: событие(), если_игрок.*, игрок.*).\n"
        f"- Файлы можно создавать/изменять только в папке сессии.\n"
        f"  - абсолютный путь: {session_dir}\n"
        f"  - относительный путь для write_file/read_file/check_compilation: {session_rel}/...\n"
        "- Нельзя редактировать существующие файлы репозитория.\n"
    )

    # Add an encoding-safe, explicit section for local models.
    system_native += (
        "\n\nAGENT WORKFLOW (strict, no stubs):\n"
        "- Before writing code, always discover actions via tools: list_modules -> search_api/list_funcs -> get_sig.\n"
        "- Never invent module.func names; only use what the tools show.\n"
        "- If a primitive does not exist, synthesize it from existing primitives and say which ones you used.\n"
        "- write_file will reject invalid MLDSL and empty plans; fix and retry.\n"
    )

    # Ensure we always have readable RU guidance (some legacy strings may be garbled by encoding).
    if builder_mode:
        system_native += (
            "\n\nЖЁСТКИЕ ПРАВИЛА (builder mode):\n"
            "- Не пиши сырой MLDSL/DSL-текст. Пиши только tool calls.\n"
            "- Всегда используй ТОЛЬКО существующие модули/функции из api_aliases.\n"
            "- Перед вызовом функции делай get_sig(module, func) и строго следуй params/enums.\n"
            "- Enum значения: используй ТОЛЬКО ключи из enums[*].options.\n"
            "- Схема: new_program или create_file -> begin_* -> add_action/set_var -> end_* -> finalize_program или save_program.\n"
            "- Закрывай блоки строго по id (end_event/end_if/end_loop/end_select/end_function).\n"
            "- Условия if: только <, <=, >, >=. Нельзя ==/!=. Для равенства используй диапазон: and_(x>=N, x<=N).\n"
        )
    else:
        system_native += (
            "\n\nЖЁСТКИЕ ПРАВИЛА (добавка):\n"
            "- Используй только существующие модули/функции из api_aliases.\n"
            "- Перед использованием функции обязательно вызови get_sig(module, func) и следуй params/enums.\n"
            "- Enum значения: используй ТОЛЬКО ключи из enums[*].options.\n"
            "- Перед write_file сначала вызови validate_mldsl(content) и исправь ошибки/варны.\n"
            "- Никаких ключевых слов: конец/иначе/then/endif — в MLDSL только фигурные скобки { }.\n"
            "- После генерации файла обязательно сделай check_compilation.\n"
            "\n"
            "Пример синтаксиса:\n"
            "```mldsl\n"
            "event(\"Вход игрока\") {\n"
            "    игрок.сообщение(\"Привет!\")\n"
            "    if_player.имеет_право(право_для_проверки=\"Белый список\") {\n"
            "        игрок.выдать_предметы(item(\"minecraft:stick\", count=1, name=\"§6Палка\"))\n"
            "    }\n"
            "}\n"
            "```\n"
        )

    # Always append a readable "strict API" section (encoding-safe).
    system_native += (
        "\n\nSTRICT API RULES (важно):\n"
        "1) Перед тем как писать/править MLDSL, получи сигнатуры действий через get_sig() и описание через get_doc() для ВСЕХ функций, которые собираешься использовать.\n"
        "2) Используй поля menu/sign2/description из get_sig(), чтобы не путать похожие действия (например, \"Заполнить область\" vs алгоритм линии).\n"
        "3) Нельзя использовать несуществующие функции/параметры/enum-значения. Если нет подходящего действия в API — спроси пользователя.\n"
        "4) После записи файла ОБЯЗАТЕЛЬНО запускай check_compilation() и исправляй ошибки до ok=true.\n"
    )

    # Synthesis/verbosity UI: optional, but helps weaker models structure their work.
    system_native += (
        "\nSYNTHESIS UI (optional):\n"
        "- Use log_thought({\"text\": \"...\"}) for short status updates.\n"
        "- Call enter_synthesis({\"reason\": \"...\"}) right before you start writing the final program/file.\n"
        "- Call exit_synthesis({\"summary\": \"...\"}) when you are done.\n"
    )

    system_native += (
        "\nTASK WORKFLOW (recommended):\n"
        "- Start with create_tasks({\"items\": [...]}) and keep tasks updated with update_task().\n"
        "- Use resolve_target() / dump_module() / get_sig() / get_doc() to verify actions and their args before writing code.\n"
        "- Prefer many small tool calls over guessing.\n"
    )

    system_native += (
        "\nCONTEXT TIP:\n"
        "- list_funcs() can be very large. Use list_funcs(module, preview_args=2, limit=50) to avoid context overflow.\n"
        "- Prefer dump_module(module, limit=50) and only call get_sig/get_doc for the specific functions you will use.\n"
    )

    # Some ollama models (e.g. nanbeige) do not support native tools. Provide an XML tool protocol fallback.
    tool_list = (
        "Доступные инструменты:\n"
        "- session_info: {}\n"
        "- list_modules: {}\n"
        "- create_tasks: {\"items\": [{\"title\": \"...\", \"details\": \"...\"}]}\n"
        "- list_tasks: {}\n"
        "- update_task: {\"task_id\": \"t1\", \"status\": \"in_progress\", \"note\": \"...\"}\n"
        "- log_thought: {\"text\": \"...\"}\n"
        "- enter_synthesis: {\"reason\": \"...\"}\n"
        "- exit_synthesis: {\"summary\": \"...\"}\n"
        "- search_api: {\"query\": \"сообщение\", \"limit\": 10, \"by_description\": true, \"by_sign\": true}\n"
        "- list_funcs: {\"module\": \"if_player\", \"preview_args\": 2, \"limit\": 60}\n"
        "- resolve_target: {\"target\": \"player.message\"}\n"
        "- dump_module: {\"module\": \"player\", \"limit\": 200}\n"
        "- get_doc: {\"module\": \"если_игрок\", \"func\": \"сообщение_равно\"}\n"
        "- check_compilation: {\"path\": \"main.mldsl\"}\n"
        "- read_file: {\"path\": \"main.mldsl\"}\n"
        + (
            "- write_file: {\"path\": \"main.mldsl\", \"content\": \"...\"}\n"
            if allow_write
            else ""
        )
    )
    # Override tool list shown to the model (include get_sig + keep readable RU).
    tool_list = (
        "Доступные инструменты:\n"
        "- session_info: {}\n"
        "- list_modules: {}\n"
        "- create_tasks: {\"items\": [{\"title\": \"...\", \"details\": \"...\"}]}\n"
        "- list_tasks: {}\n"
        "- update_task: {\"task_id\": \"t1\", \"status\": \"in_progress\", \"note\": \"...\"}\n"
        "- log_thought: {\"text\": \"...\"}\n"
        "- enter_synthesis: {\"reason\": \"...\"}\n"
        "- exit_synthesis: {\"summary\": \"...\"}\n"
        "- search_api: {\"query\": \"сообщение\", \"limit\": 10, \"by_description\": true, \"by_sign\": true}\n"
        "- list_funcs: {\"module\": \"player\", \"preview_args\": 2, \"limit\": 60}\n"
        "- resolve_target: {\"target\": \"player.message\"}\n"
        "- dump_module: {\"module\": \"player\", \"limit\": 200}\n"
        "- get_sig: {\"module\": \"player\", \"func\": \"message\"}\n"
        "- validate_mldsl: {\"content\": \"...\"}\n"
        "- get_doc: {\"module\": \"player\", \"func\": \"message\"}\n"
        "- check_compilation: {\"path\": \"main.mldsl\"}\n"
        "- read_file: {\"path\": \"main.mldsl\"}\n"
        + (
            "- write_file: {\"path\": \"main.mldsl\", \"content\": \"...\"}\n"
            if allow_write
            else ""
        )
    )

    # Builder-mode: override the tool list shown to the model (avoid mentioning write_file).
    if builder_mode:
        tool_list = (
            "Доступные инструменты (builder mode, без raw write_file):\n"
            "- session_info: {}\n"
            "- list_modules: {}\n"
            "- create_tasks: {\"items\": [{\"title\": \"...\", \"details\": \"...\"}]}\n"
            "- list_tasks: {}\n"
            "- update_task: {\"task_id\": \"t1\", \"status\": \"in_progress\", \"note\": \"...\"}\n"
            "- log_thought: {\"text\": \"...\"}\n"
            "- enter_synthesis: {\"reason\": \"...\"}\n"
            "- exit_synthesis: {\"summary\": \"...\"}\n"
            "- list_funcs: {\"module\": \"player\", \"preview_args\": 2, \"limit\": 60}\n"
            "- resolve_target: {\"target\": \"player.message\"}\n"
            "- dump_module: {\"module\": \"player\", \"limit\": 200}\n"
            "- get_sig: {\"module\": \"player\", \"func\": \"message\"}\n"
            "- get_doc: {\"module\": \"player\", \"func\": \"message\"}\n"
            "- validate_mldsl: {\"content\": \"...\"}\n"
            "- new_program: {\"path\": \"main.mldsl\", \"language\": \"mldsl\"}\n"
            "- create_file: {\"path\": \"main.mldsl\", \"language\": \"mldsl\"}\n"
            "- begin_event: {\"file_id\": \"f1\", \"name\": \"Вход игрока\"}\n"
            "- start_event: {\"file_id\": \"f1\", \"name\": \"Вход игрока\"}\n"
            "- begin_if: {\"file_id\": \"f1\", \"condition\": \"x >= 1\"}\n"
            "- add_action: {\"file_id\": \"f1\", \"target\": \"player.message\", \"parameters\": {\"text\": \"hi\"}}\n"
            "- set_var: {\"file_id\": \"f1\", \"name\": \"x\", \"expr\": 1}\n"
            "- assign: {\"file_id\": \"f1\", \"name\": \"x\", \"expr\": 1}\n"
            "- begin_function: {\"file_id\": \"f1\", \"name\": \"hello\"}\n"
            "- end_if: {\"file_id\": \"f1\", \"if_id\": \"b2\"}\n"
            "- close_if: {\"file_id\": \"f1\", \"if_id\": \"b2\"}\n"
            "- end_event: {\"file_id\": \"f1\", \"event_id\": \"b1\"}\n"
            "- close_event: {\"file_id\": \"f1\", \"event_id\": \"b1\"}\n"
            "- end_function: {\"file_id\": \"f1\", \"function_id\": \"b3\"}\n"
            "- close_function: {\"file_id\": \"f1\", \"function_id\": \"b3\"}\n"
            "- finalize_program: {\"file_id\": \"f1\"}\n"
            "- save_program: {\"file_id\": \"f1\"}\n"
        )

    system_xml = (
        system_native
        + "\n"
        + "ВАЖНО (XML tool protocol):\n"
        + "Если тебе нужен инструмент, выводи РОВНО один блок и ничего больше (без <think>):\n"
        + "<tool_call>\n"
        + "{\"name\": \"list_modules\", \"arguments\": {}}\n"
        + "</tool_call>\n"
        + tool_list
        + "После tool результата продолжай.\n"
    )

    xml_forced_model: str | None = None

    def run_native() -> int:
        sync_kwargs: dict = {}
        if ollama_timeout_s is not None:
            sync_kwargs["timeout"] = float(ollama_timeout_s)
        llm_kwargs: dict = {"model": model_name, "temperature": 0}
        # Avoid passing Ollama "options" unless the user explicitly asked for them.
        if ollama_num_predict is not None:
            llm_kwargs["num_predict"] = int(ollama_num_predict)
        if ollama_num_ctx is not None:
            llm_kwargs["num_ctx"] = int(ollama_num_ctx)
        if keep_alive is not None:
            llm_kwargs["keep_alive"] = keep_alive
        if sync_kwargs:
            llm_kwargs["sync_client_kwargs"] = sync_kwargs
        llm = ChatOllama(**llm_kwargs).bind_tools(tools)
        messages = [SystemMessage(content=system_native), HumanMessage(content=request)]

        prev_step_end_t = time.time()
        for step in range(1, max_steps + 1):
            step_start_t = time.time()
            if debug:
                ui_thought(f"[debug] step {step} wait_before_step_s: {(step_start_t - prev_step_end_t):.2f}s")

            llm_start_t = time.time()
            try:
                ai = llm.invoke(messages)
            except Exception as ex:
                msg = str(ex)
                ex_name = ex.__class__.__name__
                # Ollama/ggml model incompatibility (common with some vision/experimental models).
                if "does not support tools" in msg.lower():
                    # Let the outer handler switch us to XML tool protocol.
                    raise
                if ex_name == "ResponseError" or "GGML_ASSERT" in msg:
                    eprint("[error] Ollama model failed to run (ResponseError).")
                    if "GGML_ASSERT" in msg or "seq_add()" in msg or "n_pos_per_embd" in msg:
                        eprint("This usually means the model architecture/quant is not supported by your current Ollama/llama.cpp build.")
                        eprint("Fix:")
                        eprint("- Update Ollama to the latest version, then retry.")
                        eprint("- Or pick a different (text) model known to work (e.g. qwen3-coder, qwen2.5-coder, deepseek-r1).")
                        eprint("- If this is a vision model, our agent currently uses text-only chat.")
                    else:
                        eprint(msg)
                    return 2
                raise
            llm_end_t = time.time()
            messages.append(ai)
            prev_step_end_t = time.time()
            if debug:
                meta = _get_response_meta(ai)
                ctx_max = int(ollama_num_ctx) if ollama_num_ctx is not None else None
                ui_thought(
                    f"[debug] step {step} llm_s: {(llm_end_t - llm_start_t):.2f}s  {_fmt_tokens(meta, ctx_max, (llm_end_t - llm_start_t))}"
                )
                c = getattr(ai, "content", "") or ""
                if debug_full:
                    cs = c
                else:
                    cs = c if len(c) <= 400 else c[:400] + "...(truncated)"
                ui_thought(f"[debug] step {step} model_content: {cs}")
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                content = getattr(ai, "content", "") or ""
                tool_calls = parse_tool_calls_from_content(content)
            if not tool_calls:
                content = getattr(ai, "content", "") or ""
                if not content.strip():
                    if builder_mode:
                        messages.append(
                            HumanMessage(
                                content=(
                                    "Ответ пустой. Builder mode: делай только tool calls.\n"
                                    "Схема: session_info -> create_file или new_program -> begin_* -> add_action/set_var -> end_* -> save_program или finalize_program.\n"
                                    "Пример:\n"
                                    "<tool_call>{\"name\":\"create_file\",\"arguments\":{\"path\":\"main.mldsl\",\"language\":\"mldsl\"}}</tool_call>\n"
                                )
                            )
                        )
                        continue
                    messages.append(
                        HumanMessage(
                            content=(
                                "Ответ пустой. В режиме agent нужно использовать tools.\n"
                                "Начни с `session_info`, затем `get_doc`, затем `write_file`, затем `check_compilation`."
                            )
                        )
                    )
                    continue
                # If model talks instead of calling tools, force a tool call next.
                messages.append(
                    HumanMessage(
                        content=(
                            "Нужен tool call. НЕ пиши объяснений.\n"
                            "СРАЗУ вызови инструмент `session_info`."
                        )
                    )
                )
                continue
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args") or {}
                if debug:
                    ui_thought(f"[debug] step {step} tool_call {name} args={args}")
                t_tool0 = time.time()
                res = exec_tool_call(tc)
                prev_step_end_t = time.time()
                if debug:
                    ui_thought(f"[debug] step {step} tool_s {name}: {(time.time() - t_tool0):.2f}s")
                    s = str(res)
                    if len(s) > 400:
                        s = s[:400] + "...(truncated)"
                    ui_thought(f"[debug] tool_result {name}: {s}")
                messages.append(ToolMessage(content=str(res), tool_call_id=tc.get("id", "")))
                if isinstance(res, str) and res.startswith("ERROR: unknown tool"):
                    known = ", ".join(sorted({getattr(t, "name", "") for t in tools if getattr(t, "name", None)}))
                    messages.append(
                        HumanMessage(
                            content=(
                                "Ты вызвал несуществующий tool. Используй ТОЛЬКО инструменты из списка.\n"
                                f"Доступные tools: {known}\n"
                                "Продолжай с корректным tool call."
                            )
                        )
                    )
                # If the user requested specific .mldsl files and we successfully wrote them, stop early.
                if name == "write_file" and isinstance(res, str) and res.startswith("OK: wrote "):
                    p0 = str((args or {}).get("path") or "")
                    if _mark_written(p0):
                        return 0
                if name in {"finalize_program", "save_program"} and isinstance(res, str):
                    try:
                        obj = json.loads(res)
                        if isinstance(obj, dict) and obj.get("ok") and obj.get("path"):
                            # In builder mode, a successful finalize is enough even if the request didn't specify exact filenames.
                            if builder_mode and not requested_suffixes:
                                return 0
                            if _mark_written(str(obj["path"])):
                                return 0
                    except Exception:
                        pass
                if name == "write_file" and isinstance(res, str) and "write_file path must match requested file" in res:
                    want = ", ".join(sorted(requested_suffixes)) or "<none>"
                    messages.append(
                        HumanMessage(
                            content=(
                                "ОШИБКА: ты пишешь не тот файл.\n"
                                f"Нужно записать ТОЛЬКО запрошенный файл(ы): {want}\n"
                                f"Путь должен быть внутри sessionRel, например: {session_rel}/{next(iter(requested_suffixes)) if requested_suffixes else 'main.mldsl'}\n"
                                "Если просили .dslpy - не пиши .mldsl."
                            )
                        )
                    )
        eprint(f"max_steps reached ({max_steps}).")
        return 2

    def run_xml() -> int:
        # No bind_tools here; model must emit <tool_call> JSON blocks.
        sync_kwargs: dict = {}
        if ollama_timeout_s is not None:
            sync_kwargs["timeout"] = float(ollama_timeout_s)
        llm_kwargs: dict = {
            "model": (xml_forced_model or model_name),
            "temperature": 0,
            "stop": ["</tool_call>"],
        }
        # Avoid passing Ollama "options" unless the user explicitly asked for them.
        if ollama_num_predict is not None:
            llm_kwargs["num_predict"] = int(ollama_num_predict)
        if ollama_num_ctx is not None:
            llm_kwargs["num_ctx"] = int(ollama_num_ctx)
        if keep_alive is not None:
            llm_kwargs["keep_alive"] = keep_alive
        if sync_kwargs:
            llm_kwargs["sync_client_kwargs"] = sync_kwargs
        llm = ChatOllama(**llm_kwargs)
        messages = [SystemMessage(content=system_xml), HumanMessage(content=request)]

        prev_step_end_t = time.time()
        for step in range(1, max_steps + 1):
            step_start_t = time.time()
            if debug:
                ui_thought(f"[debug] step {step} wait_before_step_s: {(step_start_t - prev_step_end_t):.2f}s")

            llm_start_t = time.time()
            if stream:
                # Stream raw model output to stderr (best-effort). Useful for seeing <think> blocks.
                parts: list[str] = []
                last_meta: dict | None = None
                if debug:
                    ui_thought(f"[debug] step {step} streaming model_content:")
                if _supports_ansi():
                    sys.stderr.write(_ansi("90"))
                last_token_t = time.time()
                last_heartbeat_t = last_token_t
                silence_limit = float(stream_max_silence_s) if stream_max_silence_s is not None else 60.0
                try:
                    iterator = llm.stream(messages)
                    for ch in iterator:
                        txt = getattr(ch, "content", None)
                        m = _get_response_meta(ch)
                        if m:
                            last_meta = m
                        now = time.time()
                        if now - last_heartbeat_t >= 5.0 and now - last_token_t >= 5.0:
                            # Some models "think" for a while with no output; print a heartbeat so it doesn't look frozen.
                            sys.stderr.write(_fmt("90", "\n· (stream) waiting for output...\n"))
                            try:
                                sys.stderr.flush()
                            except Exception:
                                pass
                            last_heartbeat_t = now
                        if now - last_token_t >= silence_limit:
                            raise TimeoutError(f"no stream output for {silence_limit:.0f}s")
                        if not txt:
                            continue
                        parts.append(txt)
                        sys.stderr.write(txt)
                        try:
                            sys.stderr.flush()
                        except Exception:
                            pass
                        last_token_t = now
                except Exception as ex:
                    # Common failure: Ollama closes the connection mid-stream (RemoteProtocolError / incomplete chunked read).
                    msg = str(ex)
                    ex_name = ex.__class__.__name__
                    if ex_name == "ResponseError" or "GGML_ASSERT" in msg:
                        eprint("[error] Ollama model failed to stream (ResponseError).")
                        if "GGML_ASSERT" in msg or "seq_add()" in msg or "n_pos_per_embd" in msg:
                            eprint("Model incompatibility with your Ollama/llama.cpp build (or unsupported vision model).")
                            eprint("Try updating Ollama or switching models.")
                        else:
                            eprint(msg)
                        return 2
                    if "incomplete chunked read" in msg.lower() or "peer closed connection" in msg.lower() or ex_name in {"RemoteProtocolError", "ReadTimeout", "TimeoutError"}:
                        eprint("[error] Ollama stream failed (connection closed / timeout).")
                        eprint("Likely causes:")
                        eprint("- Model/server crash or OOM (too high --num-ctx / VRAM pressure).")
                        eprint("- Model produced no output for too long.")
                        eprint("Tips:")
                        eprint("- Remove --num-ctx or try a smaller value (e.g. 4096).")
                        eprint("- Reduce load: close other GPU apps; restart ollama.")
                        eprint("- Disable streaming for this model (omit --stream).")
                        eprint("- Adjust silence limit: --stream-max-silence 120")
                        return 2
                    raise
                if _supports_ansi():
                    sys.stderr.write(_ansi("0"))
                sys.stderr.write("\n")
                try:
                    sys.stderr.flush()
                except Exception:
                    pass
                ai = AIMessage(content="".join(parts), response_metadata=(last_meta or {}))
            else:
                try:
                    ai = llm.invoke(messages)
                except Exception as ex:
                    msg = str(ex)
                    ex_name = ex.__class__.__name__
                    if ex_name == "ResponseError" or "GGML_ASSERT" in msg:
                        eprint("[error] Ollama model failed to run (ResponseError).")
                        if "GGML_ASSERT" in msg or "seq_add()" in msg or "n_pos_per_embd" in msg:
                            eprint("Model incompatibility with your Ollama/llama.cpp build (or unsupported vision model).")
                            eprint("Try updating Ollama or switching models.")
                        else:
                            eprint(msg)
                        return 2
                    raise
            llm_end_t = time.time()
            messages.append(ai)
            prev_step_end_t = time.time()
            content = getattr(ai, "content", "") or ""
            if debug:
                meta = _get_response_meta(ai)
                ctx_max = int(ollama_num_ctx) if ollama_num_ctx is not None else None
                ui_thought(
                    f"[debug] step {step} llm_s: {(llm_end_t - llm_start_t):.2f}s  {_fmt_tokens(meta, ctx_max, (llm_end_t - llm_start_t))}"
                )
                if debug_full:
                    cs = content
                else:
                    cs = content if len(content) <= 400 else content[:400] + "...(truncated)"
                ui_thought(f"[debug] step {step} model_content: {cs}")

            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                tool_calls = parse_tool_calls_from_content(content)
            if not tool_calls:
                # Force tool usage in XML mode unless the model clearly produced a final answer.
                if not content.strip():
                    if builder_mode:
                        messages.append(
                            HumanMessage(
                                content=(
                                    "Ответ пустой. Builder mode: пиши только tool calls.\n"
                                    "Начни с:\n"
                                    "<tool_call>{\"name\":\"session_info\",\"arguments\":{}}</tool_call>"
                                )
                            )
                        )
                    else:
                        messages.append(HumanMessage(content="Ответ пустой. СРАЗУ выведи <tool_call>{...}</tool_call>."))
                    continue
                # If it didn't call tools, nudge it to do so (do not accept long reasoning).
                messages.append(
                    HumanMessage(
                        content=(
                            "Нужен tool call. НЕ пиши объяснений/размышлений.\n"
                            "Выведи РОВНО один блок:\n"
                            "<tool_call>{\"name\":\"session_info\",\"arguments\":{}}</tool_call>"
                        )
                    )
                )
                continue

            # Execute tool calls and feed results back as plain messages.
            for tc in tool_calls:
                if debug:
                    ui_thought(f"[debug] step {step} tool_call {tc.get('name')} args={tc.get('args')}")
                t_tool0 = time.time()
                res = exec_tool_call(tc)
                prev_step_end_t = time.time()
                if debug:
                    ui_thought(f"[debug] step {step} tool_s {tc.get('name')}: {(time.time() - t_tool0):.2f}s")
                    s = res if len(res) <= 400 else res[:400] + "...(truncated)"
                    ui_thought(f"[debug] tool_result {tc.get('name')}: {s}")
                if (
                    tc.get("name") == "get_sig"
                    and isinstance(res, str)
                    and "ValidationError" in res
                    and ("Field required" in res or "field required" in res.lower())
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "get_sig принимает ТОЛЬКО два аргумента: module и func.\n"
                                "Пример:\n"
                                "<tool_call>{\"name\":\"get_sig\",\"arguments\":{\"module\":\"if_player\",\"func\":\"имеет_право\"}}</tool_call>\n"
                                "Если нужно несколько сигнатур — вызывай get_sig несколько раз (по одной)."
                            )
                        )
                    )
                if (
                    tc.get("name") == "write_file"
                    and isinstance(res, str)
                    and "write_file path must match requested file" in res
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "write_file.path должен быть РЕАЛЬНЫМ путём (строкой), без выражений.\n"
                                f"Используй ровно: {session_rel}/main.mldsl\n"
                                "Пример:\n"
                                f"<tool_call>{{\"name\":\"write_file\",\"arguments\":{{\"path\":\"{session_rel}/main.mldsl\",\"content\":\"<MLDSL>\"}}}}</tool_call>"
                            )
                        )
                    )
                messages.append(
                    HumanMessage(
                        content=(
                            "<tool_result>\n"
                            + json.dumps(
                                {"name": tc.get("name"), "result": res},
                                ensure_ascii=False,
                            )
                            + "\n</tool_result>"
                        )
                    )
                )
                # Anti-loop: some models keep calling new_program repeatedly. Force them forward.
                if (
                    builder_mode
                    and tc.get("name") in {"new_program", "create_file", "create_program"}
                    and isinstance(res, str)
                    and '"reused": true' in res
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "ХВАТИТ вызывать new_program/create_file. Программа уже создана.\n"
                                "СЕЙЧАС сделай ОДИН tool call:\n"
                                "<tool_call>{\"name\":\"list_funcs\",\"arguments\":{\"module\":\"if_player\"}}</tool_call>"
                            )
                        )
                    )
                if isinstance(res, str) and res.startswith("ERROR: unknown tool"):
                    known = ", ".join(sorted({getattr(t, "name", "") for t in tools if getattr(t, "name", None)}))
                    messages.append(
                        HumanMessage(
                            content=(
                                "Ты вызвал несуществующий tool. Используй ТОЛЬКО инструменты из списка.\n"
                                f"Доступные tools: {known}\n"
                                "Продолжай с корректным tool call."
                            )
                        )
                    )
                if tc.get("name") == "write_file" and isinstance(res, str) and res.startswith("OK: wrote "):
                    p0 = str((tc.get("args") or {}).get("path") or "")
                    if _mark_written(p0):
                        return 0
                if tc.get("name") in {"finalize_program", "save_program"} and isinstance(res, str):
                    try:
                        obj = json.loads(res)
                        if isinstance(obj, dict) and obj.get("ok") and obj.get("path"):
                            if builder_mode and not requested_suffixes:
                                return 0
                            if _mark_written(str(obj["path"])):
                                return 0
                    except Exception:
                        pass
                if tc.get("name") == "write_file" and isinstance(res, str) and "write_file path must match requested file" in res:
                    want = ", ".join(sorted(requested_suffixes)) or "<none>"
                    messages.append(
                        HumanMessage(
                            content=(
                                "ОШИБКА: ты пишешь не тот файл.\n"
                                f"Нужно записать ТОЛЬКО запрошенный файл(ы): {want}\n"
                                f"Путь должен быть внутри sessionRel, например: {session_rel}/{next(iter(requested_suffixes)) if requested_suffixes else 'main.mldsl'}\n"
                                "Если просили .dslpy — не пиши .mldsl."
                            )
                        )
                    )

        eprint(f"max_steps reached ({max_steps}).")
        return 2

    def _llama_norm_base(url: str | None) -> str:
        u = (url or "").strip().rstrip("/")
        if not u:
            u = "http://127.0.0.1:8080"
        if not u.endswith("/v1"):
            u = u + "/v1"
        return u

    def _llama_list_models(base_url: str, timeout_s: float) -> list[str]:
        try:
            r = requests.get(base_url + "/models", timeout=timeout_s)
            r.raise_for_status()
            data = r.json() or {}
            out: list[str] = []
            for m in (data.get("data") or []):
                if isinstance(m, dict):
                    mid = m.get("id")
                    if isinstance(mid, str) and mid.strip():
                        out.append(mid.strip())
            return out
        except Exception:
            return []

    def _llama_chat_payload(
        msgs: list,
        model: str,
        stop_seq: list[str] | None,
        max_tokens: int | None,
    ) -> dict:
        def _role(m) -> str:
            cn = m.__class__.__name__
            if cn == "SystemMessage":
                return "system"
            if cn == "HumanMessage":
                return "user"
            if cn == "AIMessage":
                return "assistant"
            return "user"

        out_msgs: list[dict] = []
        for m in msgs:
            out_msgs.append({"role": _role(m), "content": getattr(m, "content", "") or ""})

        payload: dict[str, Any] = {
            "model": model,
            "messages": out_msgs,
            "temperature": 0.0,
        }
        if stop_seq:
            payload["stop"] = stop_seq
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        return payload

    def run_llama_xml(model_hint: str) -> int:
        """
        llama.cpp `llama-server` OpenAI-compatible API.
        Use XML tool protocol (no native tools).
        Activate by passing --model llama:<id> (or llama_cpp:<id>) and optionally --llama-url.
        """
        base = _llama_norm_base(llama_url)
        timeout_s = float(ollama_timeout_s) if ollama_timeout_s is not None else 120.0
        max_tokens = int(ollama_num_predict) if ollama_num_predict is not None else None
        stop_seq = ["</tool_call>"]

        # Wait for llama-server to finish loading the model (it returns 503 {"error":{"message":"Loading model"}}).
        t0_ready = time.time()
        models: list[str] = []
        while True:
            models = _llama_list_models(base, min(30.0, timeout_s))
            if models:
                break
            # If /models is unavailable, try to detect "Loading model" and wait.
            try:
                r = requests.get(base + "/models", timeout=min(10.0, timeout_s))
                if r.status_code == 503 and "Loading model" in (r.text or ""):
                    if debug:
                        ui_thought("[debug] llama-server is loading model; waiting...")
                    if time.time() - t0_ready > max(60.0, timeout_s):
                        eprint("[error] llama-server still loading model (timeout).")
                        eprint(f"URL: {base}")
                        return 2
                    time.sleep(2.0)
                    continue
            except Exception:
                pass
            break

        model = (model_hint or "").strip() or (models[0] if models else "llama")

        def _invoke(msgs):
            payload = _llama_chat_payload(msgs, model, stop_seq, max_tokens)
            # Retry while llama-server is still loading.
            last_err: Exception | None = None
            for _ in range(60):
                try:
                    r = requests.post(base + "/chat/completions", json=payload, timeout=timeout_s)
                    if r.status_code == 503 and "Loading model" in (r.text or ""):
                        time.sleep(2.0)
                        continue
                    # Common llama.cpp failure when context is too small.
                    if r.status_code == 400 and "exceeds the available context size" in (r.text or ""):
                        raise RuntimeError("LLAMA_CONTEXT_OVERFLOW: " + (r.text or "").strip())
                    r.raise_for_status()
                    break
                except Exception as ex:
                    last_err = ex
                    time.sleep(1.0)
            else:
                if last_err:
                    raise last_err
                raise RuntimeError("llama-server request failed")
            data = r.json() or {}
            content = ""
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                mm = choices[0].get("message") or {}
                if isinstance(mm, dict):
                    content = mm.get("content") or ""
            usage = data.get("usage") or {}
            meta = {}
            if isinstance(usage, dict):
                if "prompt_tokens" in usage:
                    meta["prompt_eval_count"] = usage.get("prompt_tokens")
                if "completion_tokens" in usage:
                    meta["eval_count"] = usage.get("completion_tokens")
            return AIMessage(content=content, response_metadata=meta)

        def _stream(msgs):
            payload = _llama_chat_payload(msgs, model, stop_seq, max_tokens)
            payload["stream"] = True
            with requests.post(base + "/chat/completions", json=payload, stream=True, timeout=timeout_s) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    s = line.strip()
                    if not s.startswith("data:"):
                        continue
                    s = s[5:].strip()
                    if s == "[DONE]":
                        break
                    try:
                        obj = json.loads(s)
                    except Exception:
                        continue
                    choices = obj.get("choices") or []
                    if not choices or not isinstance(choices[0], dict):
                        continue
                    delta = choices[0].get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    txt = delta.get("content")
                    if txt:
                        yield AIMessage(content=str(txt))

        messages = [SystemMessage(content=system_xml), HumanMessage(content=request)]
        prev_step_end_t = time.time()
        for step in range(1, max_steps + 1):
            step_start_t = time.time()
            if debug:
                ui_thought(f"[debug] step {step} wait_before_step_s: {(step_start_t - prev_step_end_t):.2f}s")
            llm_start_t = time.time()
            if stream:
                parts: list[str] = []
                if debug:
                    ui_thought(f"[debug] step {step} streaming model_content:")
                if _supports_ansi():
                    sys.stderr.write(_ansi("90"))
                last_token_t = time.time()
                last_heartbeat_t = last_token_t
                silence_limit = float(stream_max_silence_s) if stream_max_silence_s is not None else 60.0
                try:
                    for ch in _stream(messages):
                        txt = getattr(ch, "content", None)
                        now = time.time()
                        if now - last_heartbeat_t >= 5.0 and now - last_token_t >= 5.0:
                            sys.stderr.write(_fmt("90", "\n· (stream) waiting for output...\n"))
                            try:
                                sys.stderr.flush()
                            except Exception:
                                pass
                            last_heartbeat_t = now
                        if now - last_token_t >= silence_limit:
                            raise TimeoutError(f"no stream output for {silence_limit:.0f}s")
                        if not txt:
                            continue
                        parts.append(txt)
                        sys.stderr.write(txt)
                        try:
                            sys.stderr.flush()
                        except Exception:
                            pass
                        last_token_t = now
                except Exception as ex:
                    eprint("[error] llama-server stream failed.")
                    eprint(str(ex))
                    eprint(f"Tip: make sure llama-server is running: {base}")
                    return 2
                if _supports_ansi():
                    sys.stderr.write(_ansi("0"))
                sys.stderr.write("\n")
                try:
                    sys.stderr.flush()
                except Exception:
                    pass
                ai = AIMessage(content="".join(parts))
            else:
                try:
                    ai = _invoke(messages)
                except Exception as ex:
                    # If llama.cpp refuses due to context overflow, trim old tool chatter and retry once.
                    if "LLAMA_CONTEXT_OVERFLOW" in str(ex):
                        # Keep system + user request + last 12 messages (best-effort).
                        keep_tail = 12
                        messages = messages[:2] + messages[-keep_tail:]
                        try:
                            ai = _invoke(messages)
                        except Exception:
                            eprint("[error] llama-server request failed (context overflow).")
                            eprint("Tip: start llama-server with a larger context, e.g. `-c 16384`.")
                            return 2
                    else:
                        eprint("[error] llama-server request failed.")
                        eprint(str(ex))
                        eprint(f"Tip: make sure llama-server is running: {base}")
                        return 2
            llm_end_t = time.time()
            messages.append(ai)
            prev_step_end_t = time.time()
            content = getattr(ai, "content", "") or ""
            if debug:
                meta = _get_response_meta(ai)
                ui_thought(
                    f"[debug] step {step} llm_s: {(llm_end_t - llm_start_t):.2f}s  {_fmt_tokens(meta, None, (llm_end_t - llm_start_t))}"
                )
                if debug_full:
                    cs = content
                else:
                    cs = content if len(content) <= 400 else content[:400] + "...(truncated)"
                ui_thought(f"[debug] step {step} model_content: {cs}")

            tool_calls = parse_tool_calls_from_content(content)
            if not tool_calls:
                if not content.strip():
                    messages.append(
                        HumanMessage(
                            content=(
                                "Ответ пустой. XML mode: выведи РОВНО один <tool_call>{...}</tool_call>.\n"
                                "<tool_call>{\"name\":\"session_info\",\"arguments\":{}}</tool_call>"
                            )
                        )
                    )
                    continue
                messages.append(
                    HumanMessage(
                        content=(
                            "Нужен tool call. НЕ пиши объяснений.\n"
                            "<tool_call>{\"name\":\"session_info\",\"arguments\":{}}</tool_call>"
                        )
                    )
                )
                continue

            for tc in tool_calls:
                if debug:
                    ui_thought(f"[debug] step {step} tool_call {tc.get('name')} args={tc.get('args')}")
                t_tool0 = time.time()
                res = exec_tool_call(tc)
                prev_step_end_t = time.time()
                if debug:
                    ui_thought(f"[debug] step {step} tool_s {tc.get('name')}: {(time.time() - t_tool0):.2f}s")
                    s = res if len(res) <= 400 else res[:400] + "...(truncated)"
                    ui_thought(f"[debug] tool_result {tc.get('name')}: {s}")
                if (
                    tc.get("name") == "get_sig"
                    and isinstance(res, str)
                    and "ValidationError" in res
                    and ("Field required" in res or "field required" in res.lower())
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "get_sig принимает ТОЛЬКО два аргумента: module и func.\n"
                                "Пример:\n"
                                "<tool_call>{\"name\":\"get_sig\",\"arguments\":{\"module\":\"if_player\",\"func\":\"имеет_право\"}}</tool_call>\n"
                                "Если нужно несколько сигнатур — вызывай get_sig несколько раз (по одной)."
                            )
                        )
                    )
                if (
                    tc.get("name") == "write_file"
                    and isinstance(res, str)
                    and "write_file path must match requested file" in res
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "write_file.path должен быть РЕАЛЬНЫМ путём (строкой), без выражений.\n"
                                f"Используй ровно: {session_rel}/main.mldsl\n"
                                "Пример:\n"
                                f"<tool_call>{{\"name\":\"write_file\",\"arguments\":{{\"path\":\"{session_rel}/main.mldsl\",\"content\":\"<MLDSL>\"}}}}</tool_call>"
                            )
                        )
                    )
                messages.append(
                    HumanMessage(
                        content=(
                            "<tool_result>\n"
                            + json.dumps({"name": tc.get("name"), "result": res}, ensure_ascii=False)
                            + "\n</tool_result>"
                        )
                    )
                )
                if (
                    builder_mode
                    and tc.get("name") in {"new_program", "create_file", "create_program"}
                    and isinstance(res, str)
                    and '"reused": true' in res
                ):
                    messages.append(
                        HumanMessage(
                            content=(
                                "ХВАТИТ вызывать new_program/create_file. Программа уже создана.\n"
                                "СЕЙЧАС сделай ОДИН tool call:\n"
                                "<tool_call>{\"name\":\"list_funcs\",\"arguments\":{\"module\":\"if_player\"}}</tool_call>"
                            )
                        )
                    )
                if tc.get("name") == "write_file" and isinstance(res, str) and res.startswith("OK: wrote "):
                    p0 = str((tc.get("args") or {}).get("path") or "")
                    if _mark_written(p0):
                        return 0
        eprint(f"max_steps reached ({max_steps}).")
        return 2

    def _load_gemini_key() -> str | None:
        # priority: paid env -> default env -> fallback env
        for env_name in ("gemini_paid_key", "GEMINI_API_KEY", "gemini_api_key"):
            v = os.getenv(env_name)
            if v and v.strip():
                return v.strip()
        for fname in ("gemini_paid_key", "gemini_api_key"):
            p = (REPO_ROOT / fname)
            if p.exists():
                try:
                    t = p.read_text(encoding="utf-8").strip()
                except Exception:
                    t = p.read_text(errors="ignore").strip()
                if t:
                    return t
        return None

    def _load_groq_key() -> str | None:
        # priority: env -> file
        for env_name in ("GROQ_API_KEY", "groq_api_key"):
            v = os.getenv(env_name)
            if v and v.strip():
                return v.strip()
        for fname in ("groq_api_key", "groq_paid_key"):
            p = (REPO_ROOT / fname)
            if p.exists():
                try:
                    t = p.read_text(encoding="utf-8").strip()
                except Exception:
                    t = p.read_text(errors="ignore").strip()
                if t:
                    return t
        return None

    def _gemini_generate(model: str, prompt: str) -> str:
        key = _load_gemini_key()
        if not key:
            raise RuntimeError("Gemini key not found (set GEMINI_API_KEY or create gemini_paid_key/gemini_api_key)")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "stopSequences": ["</tool_call>"],
            },
        }
        headers = {"x-goog-api-key": key}
        last_err: Exception | None = None
        last_status: int | None = None
        last_text: str | None = None
        for attempt in range(6):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=90)
                if r.status_code in (429, 503):
                    # Rate limited / temporarily unavailable.
                    last_status = r.status_code
                    last_text = (r.text or "")[-800:]
                    time.sleep(min(30, 2 ** attempt))
                    continue
                r.raise_for_status()
                data = r.json() or {}
                break
            except Exception as ex:
                last_err = ex
                # Backoff on transient errors.
                time.sleep(min(30, 2 ** attempt))
        else:
            if last_status in (429, 503):
                raise RuntimeError(f"Gemini rate-limited/unavailable (status={last_status}). Try again later. {last_text or ''}")
            raise RuntimeError(f"Gemini request failed: {type(last_err).__name__ if last_err else 'Unknown'}: {last_err}")

        cands = data.get("candidates") or []
        if not cands:
            return ""
        parts = (((cands[0] or {}).get("content") or {}).get("parts") or [])
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "".join(texts)

    def _groq_chat(model: str, messages: list[dict]) -> str:
        key = _load_groq_key()
        if not key:
            raise RuntimeError("Groq key not found (set GROQ_API_KEY or groq_api_key, or create groq_api_key file)")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 512,
        }
        last_err: Exception | None = None
        last_status: int | None = None
        last_text: str | None = None
        for attempt in range(6):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=90)
                if r.status_code in (429, 503):
                    last_status = r.status_code
                    last_text = (r.text or "")[-800:]
                    # If API suggests retryAfter, respect it.
                    retry_s = None
                    try:
                        data = r.json() or {}
                        msg = ((data.get("error") or {}).get("message") or "")
                        m = re.search(r"Please try again in ([0-9.]+)s", msg)
                        if m:
                            retry_s = float(m.group(1))
                    except Exception:
                        retry_s = None
                    time.sleep(min(30.0, retry_s if retry_s is not None else float(2 ** attempt)))
                    continue
                if r.status_code >= 400:
                    last_status = r.status_code
                    last_text = (r.text or "")[-800:]
                r.raise_for_status()
                data = r.json() or {}
                break
            except Exception as ex:
                last_err = ex
                time.sleep(min(30, 2 ** attempt))
        else:
            if last_status in (429, 503):
                raise RuntimeError(f"Groq rate-limited/unavailable (status={last_status}). Try again later. {last_text or ''}")
            if last_status is not None:
                raise RuntimeError(
                    f"Groq request failed (status={last_status}): {type(last_err).__name__ if last_err else 'Unknown'}: {last_err}. "
                    f"{last_text or ''}"
                )
            raise RuntimeError(f"Groq request failed: {type(last_err).__name__ if last_err else 'Unknown'}: {last_err}")

        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        return (msg.get("content") or "") if isinstance(msg, dict) else ""

    def run_gemini_xml(model: str) -> int:
        # Gemini doesn't integrate with langchain tools here; we use the same XML tool protocol.
        def _find_by_alias(module: str, needle: str) -> str | None:
            mod = api.api.get(module) or {}
            want = norm_ident(needle)
            for canon, spec in mod.items():
                if want == norm_ident(canon):
                    return canon
                for a in (spec.get("aliases") or []):
                    if want == norm_ident(a):
                        return canon
            return None

        # Preload some common signatures so the model wastes fewer tool calls (reduces API requests).
        preload = []
        for mod, alias in [
            ("player", "сообщение"),
            ("player", "титл"),
            ("player", "режим_игры"),
            ("player", "выдать_предметы"),
            ("if_player", "имеет_право"),
            ("if_player", "держит"),
        ]:
            canon = api.resolve(mod, alias)
            if canon:
                preload.append(get_sig.invoke({"module": canon.module, "func": canon.canon}))
            else:
                guess = _find_by_alias(mod, alias)
                if guess:
                    preload.append(get_sig.invoke({"module": mod, "func": guess}))

        hints = (
            "Важно: `event(\"...\") { ... }` — это синтаксис MLDSL, не API-функция (НЕ вызывай get_sig для event).\n"
            f"Session paths (можно не вызывать session_info):\n- sessionRel: {session_rel}\n- sessionAbs: {str(session_dir)}\n"
            "Рекомендованный минимальный пайплайн: write_file -> check_compilation.\n"
            "Ниже подсказки по сигнатурам (можно использовать без дополнительных tool calls):\n"
            + "\n\n".join(preload[:6])
        )

        transcript: list[tuple[str, str]] = [("SYSTEM", system_xml), ("USER", request + "\n\n" + hints)]
        for step in range(1, max_steps + 1):
            time.sleep(0.8)  # soft throttle to reduce 429
            prompt_lines: list[str] = []
            for role, content in transcript[-40:]:
                prompt_lines.append(f"[{role}]")
                prompt_lines.append(content)
                prompt_lines.append("")
            prompt = "\n".join(prompt_lines).strip() + "\n"
            content = _gemini_generate(model, prompt)
            if debug:
                cs = content if len(content) <= 700 else content[:700] + "...(truncated)"
                ui_thought(f"[debug] step {step} model_content: {cs}")
            if not (content or "").strip():
                transcript.append(("USER", "Ответ пустой. СРАЗУ выведи <tool_call>{...}</tool_call> или финальный ответ."))
                continue
            tool_calls = parse_tool_calls_from_content(content)
            if not tool_calls and allow_write and any(s.endswith((".dslpy", ".dsl.py")) for s in requested_suffixes):
                s0 = (content or "").lstrip()
                looks_like_dslpy = (
                    s0.startswith("<dslpy>")
                    or s0.startswith("import dsl")
                    or s0.startswith("@dsl.")
                    or s0.startswith("@import ")
                    or s0.startswith("@template ")
                )
                if looks_like_dslpy:
                    dslpy_src = strip_markdown_code_fence(content).replace("<dslpy>", "").replace("</dslpy>", "").strip()
                    try:
                        target = next(iter(sorted(requested_suffixes)))
                        rel = f"{session_rel}/{Path(target).name}"
                        res = _write_file_impl(rel, dslpy_src + ("\n" if not dslpy_src.endswith("\n") else ""))
                        if debug:
                            eprint(f"[debug] auto_write(dslpy): {res}")
                        return 0
                    except Exception as ex:
                        eprint(f"auto-save(dslpy) failed: {type(ex).__name__}: {ex}")
                        print(dslpy_src)
                        return 2
            if not tool_calls:
                # Some Gemini configs ignore tool protocol and dump MLDSL directly.
                # If it looks like MLDSL, auto-save to main.mldsl and compile.
                # Only treat as raw MLDSL if the response *starts* with code (avoid triggering on explanations).
                s0 = (content or "").lstrip()
                looks_like_dslpy = (
                    s0.startswith("<dslpy>")
                    or s0.startswith("import dsl")
                    or s0.startswith("@dsl.")
                    or s0.startswith("@import ")
                    or s0.startswith("@template ")
                )
                if allow_write and looks_like_dslpy and any(s.endswith((".dslpy", ".dsl.py")) for s in requested_suffixes):
                    dslpy_src = strip_markdown_code_fence(content).replace("<dslpy>", "").replace("</dslpy>", "").strip()
                    try:
                        target = next(iter(sorted(requested_suffixes)))
                        rel = f"{session_rel}/{Path(target).name}"
                        res = _write_file_impl(rel, dslpy_src + ("\n" if not dslpy_src.endswith("\n") else ""))
                        if debug:
                            eprint(f"[debug] auto_write(dslpy): {res}")
                        return 0
                    except Exception as ex:
                        eprint(f"auto-save(dslpy) failed: {type(ex).__name__}: {ex}")
                        print(dslpy_src)
                        return 2
                looks_like_mldsl = s0.startswith("```") or s0.startswith("event(") or s0.startswith("событие(")
                if allow_write and looks_like_mldsl:
                    m = re.search(r'content\\s*=\\s*\"\"\"(.*?)\"\"\"', content, re.S)
                    mldsl_src = strip_markdown_code_fence((m.group(1) if m else content)).strip()
                    try:
                        v = api.validate_source(mldsl_src)
                        if not v.get("ok"):
                            eprint("MLDSL validation failed:\n" + "\n".join(v.get("errors") or []))
                            print(mldsl_src)
                            return 2
                        rel = f"{session_rel}/main.mldsl"
                        res = _write_file_impl(rel, mldsl_src + ("\n" if not mldsl_src.endswith("\n") else ""))
                        if debug:
                            eprint(f"[debug] auto_write: {res}")
                        chk = check_compilation.invoke({"path": rel})
                        print(json.dumps({"write": res, "check_compilation": json.loads(chk)}, ensure_ascii=False, indent=2))
                        return 0
                    except Exception as ex:
                        eprint(f"auto-save failed: {type(ex).__name__}: {ex}")
                        print(mldsl_src)
                        return 2

                print(content)
                return 0
            for tc in tool_calls:
                if debug:
                    ui_thought(f"[debug] step {step} tool_call {tc.get('name')} args={tc.get('args')}")
                res = exec_tool_call(tc)
                if debug:
                    s = res if len(res) <= 500 else res[:500] + "...(truncated)"
                    ui_thought(f"[debug] tool_result {tc.get('name')}: {s}")
                transcript.append(("ASSISTANT", f"<tool_call>{json.dumps({'name': tc.get('name'), 'arguments': tc.get('args')}, ensure_ascii=False)}</tool_call>"))
                transcript.append(("TOOL", str(res)))
                if tc.get("name") == "write_file" and isinstance(res, str) and res.startswith("OK: wrote "):
                    p0 = str((tc.get("args") or {}).get("path") or "")
                    if _mark_written(p0):
                        return 0
                if tc.get("name") == "finalize_program" and isinstance(res, str):
                    try:
                        obj = json.loads(res)
                        if isinstance(obj, dict) and obj.get("ok") and obj.get("path"):
                            if builder_mode and not requested_suffixes:
                                return 0
                            if _mark_written(str(obj["path"])):
                                return 0
                    except Exception:
                        pass
        eprint(f"max_steps reached ({max_steps}).")
        return 2

    def run_groq_xml(model: str) -> int:
        # Groq uses OpenAI-compatible chat completions; we still use the XML tool protocol.
        if builder_mode:
            system_groq = (
                "Ты генерируешь MLDSL ТОЛЬКО через builder tools (без сырого текста).\n"
                "Формат tool call (строго один блок):\n"
                "<tool_call>{\"name\":\"tool\",\"arguments\":{...}}</tool_call>\n"
                "После tool результата продолжай.\n"
                "Не пиши markdown/```.\n"
                "Не пиши плейсхолдеры '...' в аргументах.\n"
                "Схема: session_info -> create_file или new_program -> begin_* -> add_action/set_var -> end_* -> save_program или finalize_program.\n"
                "Закрывай блоки ТОЛЬКО по id.\n"
                "Условия if: только <, <=, >, >= (без ==/!=).\n"
                "ВАЖНО: path в create_file или new_program должен быть внутри sessionRel.\n"
                f"Пример пути: {session_rel}/main.mldsl\n"
                "\n"
                + tool_list
            )
        else:
            system_groq = (
                "Ты пишешь MLDSL и ОБЯЗАТЕЛЬНО пользуешься tools.\n"
                "Формат tool call (строго один блок):\n"
                "<tool_call>{\"name\":\"tool\",\"arguments\":{...}}</tool_call>\n"
                "После tool результата продолжай.\n"
                "Не пиши markdown/```.\n"
                "НЕ используй плейсхолдеры типа '...' в коде.\n"
                "Pipeline: validate_mldsl -> write_file -> check_compilation.\n"
                "ВАЖНО: write_file.path ДОЛЖЕН быть внутри sessionRel.\n"
                f"Используй путь ТОЛЬКО так: {session_rel}/main.mldsl\n"
                "Синтаксис MLDSL:\n"
                "event(\"Вход игрока\") {\n"
                "    игрок.сообщение(\"Привет\")\n"
                "}\n"
                "Используй только существующие модули: игрок., if_player., select., game., var., array., if_value., if_game.\n"
                "Не используй send_message/player.if_player/PlayerJoin и т.п.\n"
                "\n"
                + tool_list
            )

        transcript: list[tuple[str, str]] = [("USER", request)]
        for step in range(1, max_steps + 1):
            prompt_lines: list[str] = []
            for role, content in transcript[-12:]:
                prompt_lines.append(f"{role}: {content}")
            prompt = "\n".join(prompt_lines).strip() + "\n"
            content = _groq_chat(
                model,
                messages=[
                    {"role": "system", "content": system_groq},
                    {"role": "user", "content": prompt},
                ],
            )
            if debug:
                cs = content if len(content) <= 700 else content[:700] + "...(truncated)"
                eprint(f"[debug] step {step} model_content: {cs}")
            if not (content or "").strip():
                if builder_mode:
                    transcript.append(
                        (
                            "USER",
                            "Ответ пустой. Нужен tool call.\n"
                            "Сначала вызови session_info, затем create_file(path='<sessionRel>/main.mldsl').",
                        )
                    )
                else:
                    transcript.append(
                        (
                            "USER",
                            "Ответ пустой. Нужен tool call.\n"
                            "Сначала сгенерируй ПОЛНЫЙ MLDSL код (без '...'), затем вызови:\n"
                            "<tool_call>{\"name\":\"validate_mldsl\",\"arguments\":{\"content\":\"<MLDSL>\"}}</tool_call>",
                        )
                    )
                continue

            tool_calls = parse_tool_calls_from_content(content)
            if builder_mode:
                # In builder mode we do not accept raw MLDSL/dslpy output: only tool calls.
                if not tool_calls:
                    transcript.append(
                        (
                            "USER",
                            "Нужен tool call. В builder mode нельзя писать сырой MLDSL.\n"
                            "Схема: session_info -> create_file -> begin_event -> add_action -> end_event -> save_program.\n"
                            f"Путь для create_file: {session_rel}/main.mldsl",
                        )
                    )
                    continue

            if not tool_calls and allow_write and any(s.endswith((".dslpy", ".dsl.py")) for s in requested_suffixes):
                s0 = (content or "").lstrip()
                looks_like_dslpy = (
                    s0.startswith("<dslpy>")
                    or s0.startswith("import dsl")
                    or s0.startswith("@dsl.")
                    or s0.startswith("@import ")
                    or s0.startswith("@template ")
                )
                if looks_like_dslpy:
                    dslpy_src = strip_markdown_code_fence(content).replace("<dslpy>", "").replace("</dslpy>", "").strip()
                    try:
                        target = next(iter(sorted(requested_suffixes)))
                        rel = f"{session_rel}/{Path(target).name}"
                        res = _write_file_impl(rel, dslpy_src + ("\n" if not dslpy_src.endswith("\n") else ""))
                        if debug:
                            eprint(f"[debug] auto_write(dslpy): {res}")
                        return 0
                    except Exception as ex:
                        eprint(f"auto-save(dslpy) failed: {type(ex).__name__}: {ex}")
                        print(dslpy_src)
                        return 2
            if not tool_calls:
                # If model ignored tools, try to coerce tool usage. If it emitted raw MLDSL, auto-save.
                s0 = (content or "").lstrip()
                looks_like_mldsl = s0.startswith("```") or s0.startswith("event(") or s0.startswith("событие(")
                if allow_write and looks_like_mldsl:
                    mldsl_src = strip_markdown_code_fence(content).strip()
                    try:
                        v = api.validate_source(mldsl_src)
                        if not v.get("ok"):
                            eprint("MLDSL validation failed:\n" + "\n".join(v.get("errors") or []))
                            print(mldsl_src)
                            return 2
                        rel = f"{session_rel}/main.mldsl"
                        res = _write_file_impl(rel, mldsl_src + ("\n" if not mldsl_src.endswith("\n") else ""))
                        if debug:
                            eprint(f"[debug] auto_write: {res}")
                        chk = check_compilation.invoke({"path": rel})
                        print(json.dumps({"write": res, "check_compilation": json.loads(chk)}, ensure_ascii=False, indent=2))
                        return 0
                    except Exception as ex:
                        eprint(f"auto-save failed: {type(ex).__name__}: {ex}")
                        print(mldsl_src)
                        return 2

                transcript.append(
                    (
                        "USER",
                        "Нужен tool call. НЕ пиши объяснений.\n"
                        "Сначала сгенерируй ПОЛНЫЙ MLDSL код (без '...'), затем вызови write_file.\n"
                        "Пример формата:\n"
                        "<tool_call>{\"name\":\"write_file\",\"arguments\":{\"path\":\""
                        + session_rel
                        + "/main.mldsl\",\"content\":\"<MLDSL>\"}}</tool_call>",
                    )
                )
                continue
            for tc in tool_calls:
                if debug:
                    eprint(f"[debug] step {step} tool_call {tc.get('name')} args={tc.get('args')}")
                res = exec_tool_call(tc)
                if debug:
                    s = res if len(res) <= 500 else res[:500] + "...(truncated)"
                    eprint(f"[debug] tool_result {tc.get('name')}: {s}")
                # If it used a wrong path, immediately provide the correct one.
                if "path must be inside session dir" in (res or ""):
                    transcript.append(
                        (
                            "USER",
                            "Ты указал неправильный путь. Используй ТОЛЬКО: "
                            + session_rel
                            + "/main.mldsl",
                        )
                    )
                if "write_file path must match requested file" in (res or ""):
                    want = ", ".join(sorted(requested_suffixes)) or "<none>"
                    transcript.append(
                        (
                            "USER",
                            f"ОШИБКА: write_file должен писать ТОЛЬКО запрошенный файл(ы): {want}. "
                            f"Пиши путь внутри sessionRel, например: {session_rel}/{next(iter(requested_suffixes)) if requested_suffixes else 'main.mldsl'}",
                        )
                    )
                transcript.append(
                    ("ASSISTANT", f"<tool_call>{json.dumps({'name': tc.get('name'), 'arguments': tc.get('args')}, ensure_ascii=False)}</tool_call>")
                )
                transcript.append(("TOOL", str(res)))
                if tc.get("name") == "write_file" and isinstance(res, str) and res.startswith("OK: wrote "):
                    p0 = str((tc.get("args") or {}).get("path") or "")
                    if _mark_written(p0):
                        return 0
        eprint(f"max_steps reached ({max_steps}).")
        return 2

    def _maybe_run_planner() -> None:
        nonlocal request

        pm = (planner_model or "").strip()
        if not pm:
            return

        plan_system = (
            "You are a planning assistant for a tiny DSL compiler.\n"
            "Return ONLY strict JSON (no markdown, no code fences).\n"
            "Schema:\n"
            "{\n"
            '  \"summary\": \"...\",\n'
            '  \"lookups\": [{\"tool\":\"search_api\",\"query\":\"...\",\"by_description\":true,\"by_sign\":true}],\n'
            '  \"notes\": [\"...\"]\n'
            "}\n"
            "Keep it short. Do NOT invent API identifiers; only propose what to look up.\n"
        )

        if pm.startswith("llama:") or pm.startswith("llama_cpp:"):
            base = _llama_norm_base(planner_llama_url or llama_url)
            model = pm.split(":", 1)[1].strip()
            if not model:
                ms = _llama_list_models(base, min(30.0, float(ollama_timeout_s or 120.0)))
                model = ms[0] if ms else "llama"

            payload = _llama_chat_payload(
                [SystemMessage(content=plan_system), HumanMessage(content=request)],
                model=model,
                stop_seq=None,
                max_tokens=int(planner_max_tokens or 256),
            )
            try:
                r = requests.post(base + "/chat/completions", json=payload, timeout=float(ollama_timeout_s or 120.0))
                if r.status_code == 503 and "Loading model" in (r.text or ""):
                    time.sleep(2.0)
                    r = requests.post(base + "/chat/completions", json=payload, timeout=float(ollama_timeout_s or 120.0))
                r.raise_for_status()
                data = r.json() or {}
                content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            except Exception as ex:
                eprint("[warn] planner failed; continuing without planner.")
                eprint(str(ex))
                return

            plan_txt = (content or "").strip()
            if not plan_txt:
                return
            if len(plan_txt) > 4000:
                plan_txt = plan_txt[:4000] + "...(truncated)"
            try:
                json.loads(plan_txt)
            except Exception:
                plan_txt = json.dumps({"summary": "planner_output_not_json", "raw": plan_txt}, ensure_ascii=False)

            if debug:
                ui_thought("[debug] planner_json: " + (plan_txt if len(plan_txt) <= 400 else plan_txt[:400] + "...(truncated)"))

            request = (
                request
                + "\n\n[PLANNER_JSON]\n"
                + plan_txt
                + "\n[/PLANNER_JSON]\n"
                + "Follow the plan above. Prefer tool lookups over guessing."
            )
            return

        eprint("[warn] planner_model is set but unsupported for this provider; skipping planner.")

    # Provider selection:
    # - gemini: use XML protocol directly
    # - others: native tools, fallback to XML when needed
    # - xml:<ollama_model>: force XML tool protocol even if model supports tools
    _maybe_run_planner()
    if ir_mode:
        return run_ir_mode()
    if model_name.startswith("llama:") or model_name.startswith("llama_cpp:"):
        hint = model_name.split(":", 1)[1].strip()
        return run_llama_xml(hint)
    if model_name.startswith("gemini:"):
        return run_gemini_xml(model_name.split(":", 1)[1])
    if model_name.startswith("gemini-"):
        return run_gemini_xml(model_name)
    if model_name.startswith("groq:"):
        return run_groq_xml(model_name.split(":", 1)[1])
    if model_name.startswith("xml:"):
        model = model_name.split(":", 1)[1].strip()
        if not model:
            raise ValueError("xml: prefix requires a model name, e.g. xml:qwen3-coder")
        xml_forced_model = model
        try:
            return run_xml()
        except Exception as ex:
            msg = str(ex)
            ex_name = ex.__class__.__name__
            if ex_name in {"ReadTimeout", "TimeoutError"} or "readtimeout" in msg.lower() or "timed out" in msg.lower():
                eprint("[error] Ollama request timed out.")
                eprint("Tips:")
                eprint("- Warm the model first: `ollama run <model> \"ping\"`")
                eprint("- Try smaller output: `--num-predict 64` (or 128)")
                eprint("- Increase timeout: `--ollama-timeout 300`")
                eprint("- If still stuck, use a smaller model (e.g. qwen3:8b / qwen2.5-coder:7b).")
                return 2
            raise

    try:
        return run_native()
    except Exception as ex:
        msg = str(ex)
        # LangChain/Ollama can hang indefinitely (or very long) on some models/prompts.
        # When a timeout is configured, surface a short actionable error instead of a stack trace.
        ex_name = ex.__class__.__name__
        if ex_name in {"ReadTimeout", "TimeoutError"} or "readtimeout" in msg.lower() or "timed out" in msg.lower():
            eprint("[error] Ollama request timed out.")
            eprint("Tips:")
            eprint("- Warm the model first: `ollama run <model> \"ping\"`")
            eprint("- Try smaller output: `--num-predict 64` (or 128)")
            eprint("- Increase timeout: `--ollama-timeout 300`")
            eprint("- If still stuck, use a smaller model (e.g. qwen3:8b / qwen2.5-coder:7b).")
            return 2
        if "does not support tools" in msg.lower():
            eprint(f"[info] model '{model_name}' does not support native tools; switching to XML tool protocol")
            return run_xml()
        raise

def main() -> int:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("modules")

    ap_funcs = sub.add_parser("funcs")
    ap_funcs.add_argument("module")

    ap_doc = sub.add_parser("doc")
    ap_doc.add_argument("module")
    ap_doc.add_argument("func")

    ap_ask = sub.add_parser("ask")
    ap_ask.add_argument("question")
    ap_ask.add_argument("--use", action="append", default=[], help="module.func (or 'module func') to include in context")
    ap_ask.add_argument("--model", default="qwen3:8b")

    ap_agent = sub.add_parser("agent")
    ap_agent.add_argument("request", nargs="?", default="", help="inline request (ignored if --prompt-file is used)")
    ap_agent.add_argument("--prompt-file", default=None, help="read request from a text file (UTF-8)")
    ap_agent.add_argument("--model", default="qwen3:8b")
    ap_agent.add_argument("--max-steps", type=int, default=12)
    ap_agent.add_argument("--allow-write", action="store_true", help="allow write_file tool")
    ap_agent.add_argument("--builder", action="store_true", help="tool-only builder mode (no raw write_file)")
    ap_agent.add_argument("--ir", action="store_true", help="IR mode: модель выдаёт JSON ops[], мы сами делаем tool calls")
    ap_agent.add_argument("--template", help="prefill session main.mldsl from examples/<name>.mldsl and require staying in-template")
    ap_agent.add_argument("--ollama-timeout", type=float, default=None, help="Ollama request timeout (seconds)")
    ap_agent.add_argument("--num-predict", type=int, default=None, help="Ollama num_predict override")
    ap_agent.add_argument("--num-ctx", type=int, default=None, help="Ollama num_ctx override")
    ap_agent.add_argument("--keep-alive", default=None, help="Ollama keep_alive (e.g. 0, 300, '5m')")
    ap_agent.add_argument(
        "--llama-url",
        default=None,
        help="llama.cpp server base URL (e.g. http://127.0.0.1:8080 or http://127.0.0.1:8080/v1). Used when --model starts with llama:/llama_cpp:",
    )
    ap_agent.add_argument(
        "--planner-model",
        default=None,
        help="optional planner model (no tools). If set, it generates a short JSON plan first and injects it into the executor request.",
    )
    ap_agent.add_argument(
        "--planner-llama-url",
        default=None,
        help="llama.cpp server URL for planner (defaults to --llama-url). Only used when --planner-model starts with llama:/llama_cpp:.",
    )
    ap_agent.add_argument("--planner-max-tokens", type=int, default=256, help="planner output token budget")
    ap_agent.add_argument("--stream-max-silence", type=float, default=None, help="abort --stream if no output for N seconds (default 60)")
    ap_agent.add_argument("--stream", action="store_true", help="stream model output to stderr (best-effort; works best in XML mode)")
    ap_agent.add_argument("--debug-full", action="store_true", help="do not truncate debug model_content")
    ap_agent.add_argument("--debug", action="store_true")

    ap_prefill = sub.add_parser("prefill")
    ap_prefill.add_argument("template", help="examples/<name>.mldsl")

    ap_ui = sub.add_parser("ui-demo", help="print synthesis/thought UI demo (no LLM)")
    ap_ui.add_argument("--no-color", action="store_true", help="disable ANSI colors")

    args = ap.parse_args()
    api = ApiIndex.load()

    if args.cmd == "modules":
        return cmd_modules(api)
    if args.cmd == "funcs":
        return cmd_funcs(api, args.module)
    if args.cmd == "doc":
        return cmd_doc(api, args.module, args.func)
    if args.cmd == "ask":
        return cmd_ask(api, args.question, args.use, args.model)
    if args.cmd == "agent":
        req = (getattr(args, "request", "") or "").strip()
        prompt_file = getattr(args, "prompt_file", None)
        if prompt_file:
            p = Path(prompt_file).expanduser()
            if not p.is_absolute():
                p = (REPO_ROOT / p).resolve()
            if not p.exists() or not p.is_file():
                raise SystemExit(f"prompt file not found: {p}")
            file_text = p.read_text(encoding="utf-8", errors="replace").strip()
            if not file_text:
                raise SystemExit(f"prompt file is empty: {p}")
            req = file_text if not req else (file_text + "\n\n" + req)
        return cmd_agent(
            api,
            req,
            args.model,
            args.max_steps,
            args.allow_write,
            args.debug,
            ir_mode=bool(getattr(args, "ir", False)),
            builder_mode=bool(getattr(args, "builder", False)),
            template=getattr(args, "template", None),
            ollama_timeout_s=getattr(args, "ollama_timeout", None),
            ollama_num_predict=getattr(args, "num_predict", None),
            ollama_num_ctx=getattr(args, "num_ctx", None),
            stream=bool(getattr(args, "stream", False)),
            debug_full=bool(getattr(args, "debug_full", False)),
            keep_alive=getattr(args, "keep_alive", None),
            stream_max_silence_s=getattr(args, "stream_max_silence", None),
            llama_url=getattr(args, "llama_url", None),
            planner_model=getattr(args, "planner_model", None),
            planner_llama_url=getattr(args, "planner_llama_url", None),
            planner_max_tokens=int(getattr(args, "planner_max_tokens", 256) or 256),
        )
    if args.cmd == "prefill":
        # Shortcut to create a session containing just the template (no LLM).
        return cmd_agent(
            api,
            "prefill",
            model_name="qwen3:8b",
            max_steps=0,
            allow_write=False,
            debug=False,
            builder_mode=False,
            template=getattr(args, "template", None),
        )
    if args.cmd == "ui-demo":
        if getattr(args, "no_color", False):
            os.environ["NO_COLOR"] = "1"
        eprint(_fmt("90", "· demo thought: discovering API (list_modules/search_api/get_sig)"))
        eprint(_fmt("96", "★ SYNTHESIS ON#1: writing program"))
        eprint(_fmt("90", "· demo thought: emitting builder tool calls"))
        eprint(_fmt("96", "★ SYNTHESIS OFF: done"))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
