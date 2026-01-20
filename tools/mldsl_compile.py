import json
import re
import argparse
import ast
from pathlib import Path
import sys

API_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\out\api_aliases.json")
ALIASES_PATH = Path(r"C:\Users\ASUS\Documents\mlctmodified\src\assets\Aliases.json")
ALLACTIONS_PATH = Path(r"C:\Users\ASUS\Documents\allactions.txt")
MAX_CMD_LEN = 240


def load_api():
    return json.loads(API_PATH.read_text(encoding="utf-8"))

def warn(msg: str) -> None:
    print(f"[предупреждение] {msg}", file=sys.stderr)

def norm_ident(s: str) -> str:
    # normalization for beginner-friendly aliases:
    # - ignore case
    # - ignore underscores/spaces/dashes
    # - keep russian/latin/nums/%
    t = strip_colors(s or "").strip().lower()
    for ch in ("_", " ", "-", "\t"):
        t = t.replace(ch, "")
    return t

def strip_colors(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\u00a7.", "", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    # common mojibake fix (cp1251 bytes decoded as latin-1)
    text = text.translate(
        str.maketrans(
            {
                "à": "а",
                "á": "б",
                "â": "в",
                "ã": "г",
                "ä": "д",
                "å": "е",
                "¸": "ё",
                "æ": "ж",
                "ç": "з",
                "è": "и",
                "é": "й",
                "ê": "к",
                "ë": "л",
                "ì": "м",
                "í": "н",
                "î": "о",
                "ï": "п",
                "ð": "р",
                "ñ": "с",
                "ò": "т",
                "ó": "у",
                "ô": "ф",
                "õ": "х",
                "ö": "ц",
                "ø": "ш",
                "ù": "щ",
                "ú": "ъ",
                "û": "ы",
                "ü": "ь",
                "ý": "э",
                "þ": "ю",
                "ÿ": "я",
            }
        )
    )
    return text


def norm_key(text: str) -> str:
    text = strip_colors(text).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def load_sign1_aliases() -> dict:
    if not ALIASES_PATH.exists():
        return {}
    data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    # we store sign1 aliases here
    aliases = data.get("sign1") or {}
    return {norm_key(k): v for k, v in aliases.items()}

def load_allactions_map() -> dict:
    """
    Parses allactions.txt entries like: [(minecraft:cobblestone) Действие игрока]
    Returns normalized label -> registry id (minecraft:...)
    """
    if not ALLACTIONS_PATH.exists():
        return {}
    text = ALLACTIONS_PATH.read_text(encoding="utf-8", errors="replace")
    # Формат: [(minecraft:item) Название действия]
    pattern = re.compile(r"\[\(([^]]+)\)\s+([^]]+)\]")
    out = {}
    for match in pattern.finditer(text):
        item_id = match.group(1).strip()
        label = match.group(2).strip()
        label = strip_colors(label).strip()
        out[norm_key(label)] = item_id.strip()
    return out


def event_variant_to_name(variant: str) -> str:
    # MVP mapping; extend later
    v = (variant or "").strip().lower()
    if v in ("join", "вход"):
        return "вход"
    if v in ("leave", "quit", "выход"):
        return "выход"
    return variant

def find_action(api: dict, module: str, func: str):
    # module aliases for beginner-friendly syntax (keep minimal / RU-first)
    module_aliases = {
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
    module = module_aliases.get(norm_ident(module), module)
    mod = api.get(module)
    if not mod:
        return None, None
    # direct name
    if func in mod:
        return func, mod[func]
    # alias match
    func_n = norm_ident(func)
    for canon, spec in mod.items():
        aliases = spec.get("aliases") or []
        if func in aliases:
            return canon, spec
        # allow matching aliases without underscores (сообщениеравно vs сообщение_равно)
        if func_n and (func_n == norm_ident(canon) or any(func_n == norm_ident(a) for a in aliases)):
            return canon, spec
    return None, None

def split_args(arg_str: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    in_str = False
    esc = False
    for ch in arg_str:
        if esc:
            buf += ch
            esc = False
            continue
        if ch == "\\":
            esc = True
            buf += ch
            continue
        if ch == '"':
            in_str = not in_str
            buf += ch
            continue
        if ch == "," and not in_str:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts

def parse_call_args(arg_str: str):
    # supports: a=1, b="x", c=var_save(name), and positional: "hello", text(hi)
    kv: dict[str, str] = {}
    pos: list[str] = []
    if not arg_str.strip():
        return kv, pos
    for p in split_args(arg_str):
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            kv[k.strip()] = v
        else:
            v = p.strip()
            if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            pos.append(v)
    return kv, pos

def wrap_value(mode: str | None, value: str) -> str:
    v = (value or "").strip()
    if not v:
        return v
    # If user already passed a function-like value (text(...), var(...), num(...), etc) keep it.
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\(.*\)$", v):
        return v
    m = (mode or "").upper()
    if m == "TEXT":
        return f"text({v})"
    if m == "NUMBER":
        return f"num({v})"
    if m == "VARIABLE":
        return f"var({v})"
    if m == "LOCATION":
        return f"loc({v})"
    if m == "ARRAY":
        return f"arr({v})"
    return v


# Identifiers:
# - allow %placeholders% inside variable names (e.g. %selected%counter)
# - keep calls/modules stricter for now (no % in module/function names)
NAME_RE = r"[%%\w\u0400-\u04FF]+"
CALL_RE = re.compile(r"^\s*([\w\u0400-\u04FF]+)\.([\w\u0400-\u04FF]+)\s*\((.*)\)\s*;?\s*$")
EVENT_RE = re.compile(r"^\s*(?:event|событие)\s*\(\s*([\w\u0400-\u04FF]+)\s*\)\s*\{\s*$", re.I)
BARE_CALL_RE = re.compile(r"^\s*([\w\u0400-\u04FF]+)\s*\((.*)\)\s*;?\s*$")
FUNC_RE = re.compile(rf"^\s*(?:func|function|def|функция)\s*(?:\(\s*)?([\w\u0400-\u04FF]+)(?:\s*\))?\s*\{{\s*$", re.I)
LOOP_RE = re.compile(rf"^\s*(?:loop|цикл)\s+([\w\u0400-\u04FF]+)(?:\s+every)?\s+(\d+)\s*\{{\s*$", re.I)
ASSIGN_RE = re.compile(
    rf"^\s*(?:(save|сохранить|сохранена|сохраненная|сохранённая)\s+)?({NAME_RE})\s*(?:~\s*)?(?:(\*)\s*)?=\s*(.+?)\s*;?\s*$",
    re.I,
)
SAVE_SHORTHAND_RE = re.compile(rf"^\s*({NAME_RE})\s*~\s*(.+?)\s*;?\s*$", re.I)

IFPLAYER_RE = re.compile(r"^\s*(?:if_?player|если_?игрок)\.([\w\u0400-\u04FF]+)\s*\((.*)\)\s*\{\s*$", re.I)
SELECTOBJECT_IFPLAYER_RE = re.compile(r"^\s*SelectObject\.player\.IfPlayer\.([\w\u0400-\u04FF]+)\s*\{\s*$", re.I)
IFGAME_RE = re.compile(r"^\s*(?:if_?game|если_?игра)\.([\w\u0400-\u04FF]+)\s*\((.*)\)\s*\{\s*$", re.I)
IFGAME_OLD_RE = re.compile(r"^\s*IfGame\.([\w\u0400-\u04FF]+)\s*\{\s*$", re.I)
IF_RE = re.compile(r"^\s*if\s+(.+?)\s*\{\s*$", re.I)
IFTEXT_RE = re.compile(r"^\s*iftext\s+(.+?)\s*\{\s*$", re.I)
IFEXISTS_RE = re.compile(rf"^\s*ifexists\s*(?:\(\s*({NAME_RE})\s*\)|\s+({NAME_RE}))\s*\{{\s*$", re.I)


def spec_menu_name(spec: dict) -> str:
    return (
        strip_colors(spec.get("menu", "")).strip()
        or strip_colors(spec.get("sign2", "")).strip()
        or strip_colors(spec.get("gui", "")).strip()
    )

def is_supported_numeric_expr_ast(node) -> bool:
    """
    Numeric expression subset:
    - constants: int/float/bool
    - identifiers: Name
    - unary: +x, -x
    - binary: +, -, *, /
    """
    if node is None:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Expression):
            continue
        if isinstance(n, (ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub)):
            continue
        if isinstance(n, ast.Name):
            continue
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, bool)):
            continue
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            continue
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            continue
        # everything else (calls, attributes, %, etc) is not supported here
        return False
    return True

def safe_eval_number_expr(expr: str) -> float | None:
    try:
        node = ast.parse(expr, mode="eval")
    except Exception:
        return None

    def eval_node(n):
        if isinstance(n, ast.Expression):
            return eval_node(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = eval_node(n.operand)
            return +v if isinstance(n.op, ast.UAdd) else -v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a = eval_node(n.left)
            b = eval_node(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
        raise ValueError("unsupported")

    try:
        return eval_node(node)
    except Exception:
        return None

def flatten_mul_factors(expr: str) -> list[float] | None:
    """
    If expr is a pure multiplication tree (with optional parentheses/unary +/-),
    return the list of numeric factors (already evaluated for unary +/-). Otherwise None.
    """
    try:
        node = ast.parse(expr, mode="eval")
    except Exception:
        return None

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return [float(n.value)]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            factors = walk(n.operand)
            if factors is None:
                return None
            if isinstance(n.op, ast.USub):
                if len(factors) == 1:
                    return [-factors[0]]
                # -(a*b) can't be represented as pure multiplication of positive factors cleanly; fold
                return [-safe_eval_number_expr(expr)]
            return factors
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            a = walk(n.left)
            b = walk(n.right)
            if a is None or b is None:
                return None
            return a + b
        return None

    factors = walk(node)
    if factors is None:
        return None
    # filter None from unary fold fallback
    return [f for f in factors if f is not None]

def expr_to_operand(node, name_map: dict[str, str] | None = None) -> str:
    """
    Convert AST node to a NUMBER input expression token suitable for num(...).
    Leaves are either numeric constants or identifiers (treated as %var(name)%).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        v = node.value
        if isinstance(v, bool):
            v = int(v)
        return f"num({v})"
    if isinstance(node, ast.Name):
        var_name = (name_map or {}).get(node.id, node.id)
        # Server accepts a VARIABLE item inside NUMBER slots (it reads the value).
        return f"var({var_name})"
    # fallback: try to evaluate fully
    v = safe_eval_number_expr(ast.unparse(node) if hasattr(ast, "unparse") else "")
    if v is not None:
        if abs(v - int(v)) < 1e-9:
            return f"num({int(v)})"
        return f"num({v})"
    raise ValueError("unsupported operand in numeric expression")

def preprocess_numeric_expr(expr: str) -> tuple[str, dict[str, str]]:
    """
    Makes server-style placeholder variable names parseable by Python AST.
    Example: %selected%counter + 1  ->  __mlccv1 + 1  (with map __mlccv1 -> %selected%counter)
    """
    # %token%suffix where suffix is identifier chars; keep it conservative to avoid eating %var(...)%.
    token_re = re.compile(r"%%(?:[a-zA-Z_][a-zA-Z0-9_]*)%%[0-9A-Za-z_\u0400-\u04FF]+")
    out = expr
    mapping: dict[str, str] = {}
    idx = 0
    for m in token_re.finditer(expr):
        original = m.group(0)
        idx += 1
        safe = f"__mlccv{idx}"
        mapping[safe] = original
        out = out.replace(original, safe)
    return out, mapping

def operand_to_number_token(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty operand")
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    # numeric literal
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
        if "." in s:
            return f"num({float(s)})"
        return f"num({int(s)})"
    # already wrapped
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\(.*\)$", s):
        return s
    # variable item inside NUMBER slot works on the server
    return f"var({s})"

def operand_to_text_token(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty operand")
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return f"text({s[1:-1]})"
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
        return f"text({s})"
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\(.*\)$", s):
        return s
    return f"var({s})"

def compile_if_condition(api: dict, expr: str) -> list[tuple[list[str], dict]]:
    e = (expr or "").strip()
    if not e:
        raise ValueError("if: empty condition")

    # ifexists(var) / ifexists var / exists(var)
    m_exists = re.match(rf"^(?:ifexists|ifexists|exists)\s*\(\s*({NAME_RE})\s*\)\s*$", e, re.I) or re.match(
        rf"^(?:ifexists|exists)\s+({NAME_RE})\s*$", e, re.I
    )
    if m_exists:
        v = m_exists.group(1)
        res = compile_line(api, f"if_value.var(var=var({v}))")
        return [res]

    # range: low <= x <= high  OR  high >= x >= low
    m_range = re.match(
        rf"^(.+?)\s*(<=|<|>=|>)\s*({NAME_RE})\s*(<=|<|>=|>)\s*(.+?)$",
        e,
        re.I,
    )
    if m_range:
        a, op1, mid, op2, b = [m_range.group(i) for i in range(1, 6)]
        a = a.strip()
        b = b.strip()
        op1 = op1.strip()
        op2 = op2.strip()

        # normalize to low <= mid <= high
        if op1 in (">", ">=") and op2 in (">", ">="):
            # a >= mid >= b  => low=b, high=a
            low, high = b, a
            lower_inclusive = op2 == ">="
            upper_inclusive = op1 == ">="
        elif op1 in ("<", "<=") and op2 in ("<", "<="):
            # a <= mid <= b  (rare, but accept): low=a, high=b
            low, high = a, b
            lower_inclusive = op1 == "<="
            upper_inclusive = op2 == "<="
        else:
            # mixed directions not supported in MVP
            m_range = None

        if m_range:
            # if_value.number_2: num=checked, num2=lower, num3=upper
            num = operand_to_number_token(mid)
            num2 = operand_to_number_token(low)
            num3 = operand_to_number_token(high)
            # enums: tip_proverki_dlya_bolshe (>,≥) and tip_proverki_dlya_menshe (<,≤)
            greater = '≥ (Больше или равно)' if lower_inclusive else '> (Больше)'
            less = '≤ (Меньше или равно)' if upper_inclusive else '< (Меньше)'
            res = compile_line(
                api,
                f'if_value.number_2(num={num}, num2={num2}, num3={num3}, tip_proverki_dlya_bolshe="{greater}", tip_proverki_dlya_menshe="{less}")',
            )
            return [res]

    # simple compare: lhs op rhs (numeric)
    # Use "Сравнить число" (if_value.number_2) because its GUI layout matches:
    # - compared value
    # - lower bound (for > / >=)
    # - upper bound (for < / <=)
    m_cmp = re.match(rf"^(.+?)\s*(>=|<=|>|<)\s*(.+?)$", e, re.I)
    if m_cmp:
        lhs, op, rhs = m_cmp.group(1).strip(), m_cmp.group(2).strip(), m_cmp.group(3).strip()
        checked = operand_to_number_token(lhs)
        bound = operand_to_number_token(rhs)

        # Defaults on the server are usually strict (< and >). Only click enums for inclusive ops.
        if op in ("<", "<="):
            args = [f"num={checked}", f"num3={bound}"]
            if op == "<=":
                args.append('tip_proverki_dlya_menshe="≤ (Меньше или равно)"')
            res = compile_line(api, "if_value.number_2(" + ", ".join(args) + ")")
            return [res]
        if op in (">", ">="):
            args = [f"num={checked}", f"num2={bound}"]
            if op == ">=":
                args.append('tip_proverki_dlya_bolshe="≥ (Больше или равно)"')
            res = compile_line(api, "if_value.number_2(" + ", ".join(args) + ")")
            return [res]

    # fallback (advanced): allow direct if_value.<func>(...) by writing: if if_value.xxx(...)
    if e.startswith("if_value.") or e.startswith("if_player.") or e.startswith("if_game."):
        res = compile_line(api, e)
        return [res]

    raise ValueError(f"if: unsupported condition: {e}")

def compile_iftext_condition(api: dict, expr: str) -> list[tuple[list[str], dict]]:
    e = (expr or "").strip()
    if not e:
        raise ValueError("iftext: empty condition")

    # target == opt1 or opt2 or opt3 ...
    m = re.match(r"^(.+?)\s*(==|=)\s*(.+?)$", e, re.I)
    if not m:
        raise ValueError("iftext: expected: <target> == <a> or <b> ...")
    target_raw = m.group(1).strip()
    rest = m.group(3).strip()
    parts = [p.strip() for p in re.split(r"\bor\b|\|\|", rest, flags=re.I) if p.strip()]
    if not parts:
        raise ValueError("iftext: expected at least 1 compare text")

    target = operand_to_text_token(target_raw)
    opts = [operand_to_text_token(p) for p in parts[:7]]
    args = [f"text={target}"] + [f"text{i+2}={v}" for i, v in enumerate(opts)]
    res = compile_line(api, f"if_value.text(" + ", ".join(args) + ")")
    return [res]

def flatten_binop(node, op_type):
    out = []

    def rec(n):
        if isinstance(n, ast.BinOp) and isinstance(n.op, op_type):
            rec(n.left)
            rec(n.right)
        else:
            out.append(n)

    rec(node)
    return out

def flatten_left_assoc(node, op_type):
    """
    Flatten only the LEFT-associated chain for non-associative ops (Sub/Div).
    Keeps right subtrees intact to preserve parentheses, e.g. a-(b-c) -> [a, (b-c)].
    """
    out = []
    cur = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, op_type):
        out.append(cur.right)
        cur = cur.left
    out.append(cur)
    out.reverse()
    return out

def compile_line(api: dict, line: str):
    m = CALL_RE.match(line)
    if not m:
        return None
    module, func, arg_str = m.group(1), m.group(2), m.group(3)
    canon, spec = find_action(api, module, func)
    if not spec:
        raise ValueError(f"Unknown action: {module}.{func}")

    kv, pos = parse_call_args(arg_str)
    # map params -> slot(N)=...
    pieces = []
    params = spec.get("params") or []
    # positional args fill params in order
    if pos:
        for idx, raw in enumerate(pos):
            if idx >= len(params):
                break
            pname = params[idx]["name"]
            if pname not in kv:
                kv[pname] = raw

    for p in params:
        name = p["name"]
        if name not in kv:
            continue
        val = wrap_value(p.get("mode"), kv[name])
        pieces.append(f"slot({p['slot']})={val}")

    # enum sugar: if key matches enum name, convert to clicks(slot,n)
    for e in spec.get("enums") or []:
        ename = e.get("name")
        if not ename or ename not in kv:
            continue
        raw = kv[ename].strip().strip('"')
        opts = e.get("options") or {}
        clicks = None
        if raw in opts:
            clicks = opts[raw]
        else:
            # allow minor normalization for newbies: underscores/spaces/case.
            raw2 = raw.replace("_", " ")
            if raw2 in opts:
                clicks = opts[raw2]
            else:
                opts_norm = {norm_ident(k): v for k, v in opts.items()}
                raw_norm = norm_ident(raw)
                raw2_norm = norm_ident(raw2)
                if raw_norm in opts_norm:
                    clicks = opts_norm[raw_norm]
                elif raw2_norm in opts_norm:
                    clicks = opts_norm[raw2_norm]
        if clicks is None:
            # allow numeric
            clicks = int(raw)
        pieces.append(f"clicks({e['slot']},{clicks})=0")

    return pieces, spec

def compile_builtin(api: dict, line: str):
    m = BARE_CALL_RE.match(line)
    if not m or "." in (m.group(1) or ""):
        # assignment sugar doesn't look like a call
        m_short = SAVE_SHORTHAND_RE.match(line)
        if m_short:
            name = (m_short.group(1) or "").strip()
            rhs = (m_short.group(2) or "").strip()
            # Convert to normal assignment form handled below.
            line = f"save {name} = {rhs}"

        m_assign = ASSIGN_RE.match(line)
        if not m_assign:
            return None

        save_kw = (m_assign.group(1) or "").strip().lower()
        name = (m_assign.group(2) or "").strip()
        op = (m_assign.group(3) or "").strip()
        rhs = (m_assign.group(4) or "").strip()

        saved = False
        if save_kw in ("save", "сохранить", "сохранена", "сохраненная", "сохранённая"):
            saved = True
        # support `name~ = ...` and `name ~ = ...`
        if re.search(rf"^\s*(?:save\s+)?{re.escape(name)}\s*~", line, re.I):
            saved = True

        if not name or not rhs:
            return None

        # Determine RHS
        rhs_wrapped = rhs
        # quoted -> text
        if (rhs_wrapped.startswith('"') and rhs_wrapped.endswith('"')) or (
            rhs_wrapped.startswith("'") and rhs_wrapped.endswith("'")
        ):
            rhs_wrapped = f"text({rhs_wrapped[1:-1]})"
        else:
            # numeric constant expr -> num(result)
            v = safe_eval_number_expr(rhs_wrapped)
            if v is not None:
                # keep integer if possible
                if abs(v - int(v)) < 1e-9:
                    rhs_wrapped = f"num({int(v)})"
                else:
                    rhs_wrapped = f"num({v})"
            else:
                # default: if not func-like, treat as text
                is_func_like = False
                if rhs_wrapped.endswith(")") and "(" in rhs_wrapped:
                    prefix = rhs_wrapped.split("(", 1)[0]
                    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", prefix or ""):
                        is_func_like = True
                if not is_func_like:
                    rhs_wrapped = f"text({rhs_wrapped})"

        var_token = f"var_save({name})" if saved else f"var({name})"

        # Formula compilation: if RHS contains operators or identifiers, compile into numeric actions.
        rhs_expr = rhs
        rhs_expr_s, name_map = preprocess_numeric_expr(rhs_expr)
        try:
            node = ast.parse(rhs_expr_s, mode="eval").body
        except Exception:
            node = None

        if is_supported_numeric_expr_ast(node) and isinstance(node, (ast.BinOp, ast.UnaryOp)):
            # Compile expression into one or more actions; warn about action count.
            return compile_numeric_expression(api, target_var=var_token, expr_node=node, name_map=name_map)

        # If RHS is just a name (variable), treat it as number placeholder unless explicitly wrapped.
        if isinstance(node, ast.Name):
            rhs_wrapped = f"var({(name_map or {}).get(node.id, node.id)})"

        # If user explicitly requested multiplication assignment (name * = ...), and it's a pure mul expression,
        # compile to set_product with multiple operands.
        if op == "*":
            try:
                factors_nodes = flatten_binop(node, ast.Mult) if isinstance(node, ast.BinOp) else None
            except Exception:
                factors_nodes = None
            if factors_nodes and len(factors_nodes) >= 2:
                return compile_op_action(api, "set_product", var_token, [expr_to_operand(n) for n in factors_nodes])

        # default '=' assignment (value can be text/num/...)
        res = compile_line(api, f"var.set_value(var={var_token}, value={rhs_wrapped})")
        if not res:
            raise ValueError("assignment '=' failed: no set_value action")
        return [res]
    name = (m.group(1) or "").strip()
    arg_str = m.group(2) or ""

    def parse_bool(v: str) -> bool:
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "y", "on", "async", "асинхронно", "асинхронный")

    loop_starters = {"startloop", "start_loop", "запуститьцикл", "запустить_цикл"}
    loop_stoppers = {"stoploop", "stop_loop", "остановитьцикл", "остановить_цикл", "стопцикл", "стоп_цикл"}

    if name in loop_starters or name in loop_stoppers:
        kv, pos = parse_call_args(arg_str)
        names = []
        if pos:
            names.extend(pos)
        for v in kv.values():
            if v:
                names.append(v)
        cleaned = [n.strip() for n in names if n and n.strip()]
        if not cleaned:
            raise ValueError(f"{name}()(): expected at least 1 cycle name")

        target_funcs = (
            ("start_loops", "unnamed_8", "начать_цикл") if name in loop_starters
            else ("stop_loops", "unnamed_9", "остановить_цикл")
        )
        out = []
        for i in range(0, len(cleaned), 18):
            chunk = cleaned[i:i + 18]
            parts = []
            for idx, val in enumerate(chunk, start=1):
                key = "text" if idx == 1 else f"text{idx}"
                parts.append(f"{key}={val}")
            res = None
            for func_name in target_funcs:
                synthetic = f"game.{func_name}({', '.join(parts)})"
                res = compile_line(api, synthetic)
                if res:
                    break
            if not res:
                raise ValueError(f"{name}()(): internal compile failed")
            out.append(res)
        return out

    # Function call by name: call(name, async=true)
    call_aliases = {"call", "invoke", "вызвать", "runfunc", "run_func"}
    if name in call_aliases:
        kv, pos = parse_call_args(arg_str)
        async_flag = False
        if "async" in kv:
            async_flag = parse_bool(kv.pop("async"))
        elif "asynchronous" in kv:
            async_flag = parse_bool(kv.pop("asynchronous"))

        # Server accepts function names as plain text too; default to text() to avoid creating dynamic variables.
        pieces = []
        target = None
        if pos:
            target = pos[0] if len(pos) >= 1 else None
        if "var" in kv and (target is None):
            target = kv.get("var")
        if target is None:
            raise ValueError("call(): expected function name, e.g. call(test) or call(var(test))")

        # If user provided explicit var()/text()/... keep it; otherwise use text(name).
        target_wrapped = target.strip()
        is_func_like = False
        if target_wrapped.endswith(")") and "(" in target_wrapped:
            prefix = target_wrapped.split("(", 1)[0]
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", prefix or ""):
                is_func_like = True
        if not is_func_like:
            target_wrapped = f"text({target_wrapped})"
        pieces.append(f"slot(13)={target_wrapped}")
        if async_flag:
            pieces.append("clicks(16,1)=0")
        # Return as synthetic spec-less action so caller can still resolve sign1/sign2 via api.
        # We'll compile it through the known action to resolve block/name, but override pieces.
        res = None
        for func_name in ("call_function", "вызвать_функцию"):
            synthetic = f"game.{func_name}()"
            res = find_action(api, "game", func_name)[1]
            if res:
                break
        if not res:
            raise ValueError("call(): no call_function action in api")
        return [(pieces, res)]

    # Sugar: hello() -> call(hello)
    reserved = loop_starters | loop_stoppers | call_aliases | {"event", "func", "function", "def", "loop", "цикл", "функция"}
    if name and name not in reserved:
        kv, pos = parse_call_args(arg_str)
        async_flag = False
        if "async" in kv:
            async_flag = parse_bool(kv.pop("async"))

        pieces = [f"slot(13)=text({name})"]
        if async_flag:
            pieces.append("clicks(16,1)=0")
        spec = api.get("game", {}).get("call_function")
        if not spec:
            # fallback older name
            spec = api.get("game", {}).get("вызвать_функцию")
        if not spec:
            raise ValueError("Function call sugar failed: no call_function action in api")
        return [(pieces, spec)]

    return None

def compile_op_action(api: dict, func_name: str, target_var: str, operands: list[str]):
    """
    Emits one or more actions for a numeric op with up to 10 operands per action.
    func_name is one of: set_sum, set_difference, set_product, set_quotient.
    Operands are NUMBER expressions like num(5) or num(%var(x)%).
    """
    max_terms = 10
    if not operands:
        raise ValueError(f"{func_name}: expected operands")

    out = []
    remaining = list(operands)
    tmp_idx = 0

    # If too many operands, accumulate into temporaries.
    while len(remaining) > max_terms:
        tmp_idx += 1
        tmp_name = f"__mlcc_acc{tmp_idx}"
        chunk = remaining[:max_terms]
        remaining = remaining[max_terms:]
        out.append(compile_line(api, f"var.{func_name}(var=var({tmp_name}), " + ", ".join(_nums_kv(chunk)) + ")"))
        # next action uses tmp as first operand
        remaining = [f"num(%var({tmp_name})%)"] + remaining

    out.append(compile_line(api, f"var.{func_name}(var={target_var}, " + ", ".join(_nums_kv(remaining)) + ")"))
    return out

def _nums_kv(operands: list[str]) -> list[str]:
    parts = []
    for idx, op in enumerate(operands, start=1):
        key = "num" if idx == 1 else f"num{idx}"
        parts.append(f"{key}={op}")
    return parts

def compile_numeric_expression(
    api: dict, target_var: str, expr_node, *, name_map: dict[str, str] | None = None
) -> list[tuple[list[str], dict]]:
    """
    Compile an AST numeric expression into a list of (pieces,spec) actions.
    We use temp variables for subexpressions to preserve precedence.
    """
    actions: list[tuple[list[str], dict]] = []
    tmp_counter = 0

    def new_tmp():
        nonlocal tmp_counter
        tmp_counter += 1
        return f"__mlcc_tmp{tmp_counter}"

    def ensure_value(node) -> str:
        # If node is a leaf, return operand token.
        if isinstance(node, (ast.Constant, ast.Name)):
            return expr_to_operand(node, name_map=name_map)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)) and isinstance(node.operand, (ast.Constant, ast.Name)):
            # best-effort: evaluate unary with safe_eval
            v = safe_eval_number_expr(ast.unparse(node) if hasattr(ast, "unparse") else "")
            if v is not None:
                if abs(v - int(v)) < 1e-9:
                    return f"num({int(v)})"
                return f"num({v})"
        # Otherwise compute into temp var.
        tmp = new_tmp()
        tmp_tok = f"var({tmp})"
        compile_into(tmp_tok, node)
        return f"var({tmp})"

    def compile_into(target_tok: str, node):
        nonlocal actions
        if isinstance(node, (ast.Constant, ast.Name)):
            actions.append(
                compile_line(api, f"var.set_value(var={target_tok}, value={expr_to_operand(node, name_map=name_map)})")
            )
            return

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            if isinstance(node.op, ast.UAdd):
                compile_into(target_tok, node.operand)
                return
            # -(expr) => expr * -1
            operand = ensure_value(node.operand)
            actions.extend(compile_op_action(api, "set_product", target_tok, [operand, "num(-1)"]))
            return

        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                operands = [ensure_value(n) for n in flatten_binop(node, ast.Add)]
                actions.extend(compile_op_action(api, "set_sum", target_tok, operands))
                return
            if isinstance(node.op, ast.Mult):
                operands = [ensure_value(n) for n in flatten_binop(node, ast.Mult)]
                actions.extend(compile_op_action(api, "set_product", target_tok, operands))
                return
            if isinstance(node.op, ast.Sub):
                operands = [ensure_value(n) for n in flatten_left_assoc(node, ast.Sub)]
                actions.extend(compile_op_action(api, "set_difference", target_tok, operands))
                return
            if isinstance(node.op, ast.Div):
                operands = [ensure_value(n) for n in flatten_left_assoc(node, ast.Div)]
                actions.extend(compile_op_action(api, "set_quotient", target_tok, operands))
                return
        # leaf / unsupported: set_value with evaluated number if possible
        raw = ast.unparse(node) if hasattr(ast, "unparse") else ""
        v = safe_eval_number_expr(raw)
        if v is not None:
            val = f"num({int(v) if abs(v-int(v))<1e-9 else v})"
            res = compile_line(api, f"var.set_value(var={target_tok}, value={val})")
            actions.append(res)
            return
        raise ValueError("unsupported numeric expression")

    compile_into(target_var, expr_node)

    # Flatten compile_op_action outputs; they are already (pieces,spec) from compile_line.
    flat: list[tuple[list[str], dict]] = []
    for res in actions:
        if not res:
            continue
        flat.append(res)

    # warn: number of actions used
    if len(flat) > 1:
        extra = len(flat) - 1
        warn(f"формула для {target_var} скомпилирована в {len(flat)} действий (+{extra})")

    return flat

def build_placeadvanced_command(
    *,
    event_block: str,
    event_name: str,
    actions: list[tuple[str, str, str]],
) -> str:
    # tokens are parsed by PlaceParser.splitArgsPreserveQuotes
    parts = ["/placeadvanced", event_block, f"\"{event_name}\"", "no"]
    for block, name, args in actions:
        # Plan-only metadata can be embedded as: menu||sign1||sign2. For /placeadvanced, only menu is clickable.
        if name and "||" in name:
            name = name.split("||", 1)[0]
        parts.append(block)
        parts.append(f"\"{name}\"")
        parts.append(f"\"{args}\"" if args else "no")
    cmd = " ".join(parts)
    return cmd

def compile_entries(path: Path) -> list[dict]:
    api = load_api()
    sign1_aliases = load_sign1_aliases()
    blocks = load_allactions_map()

    def load_with_imports(p: Path, stack: list[Path]) -> list[str]:
        rp = p.resolve()
        if rp in stack:
            warn(f"циклический import: {' -> '.join(str(x.name) for x in stack + [rp])}")
            return []
        stack = [*stack, rp]
        raw_lines = p.read_text(encoding="utf-8-sig").splitlines()
        out_lines: list[str] = []
        for raw in raw_lines:
            s = raw.strip()
            if not s or s.startswith("#"):
                out_lines.append(raw)
                continue

            # import/use/include sugar
            # - использовать file
            # - use file
            # - import file
            # - import name from dir
            m = re.match(r"^(?:использовать|use|import)\s+(.+?)\s*$", s, re.I)
            if not m:
                out_lines.append(raw)
                continue

            rest = m.group(1).strip()
            src_path = None

            m_from = re.match(r"^(.+?)\s+from\s+(.+?)$", rest, re.I)
            if m_from:
                name = m_from.group(1).strip().strip('"').strip("'")
                folder = m_from.group(2).strip().strip('"').strip("'")
                src_path = (p.parent / folder / name)
            else:
                name = rest.strip().strip('"').strip("'")
                src_path = (p.parent / name)

            if src_path.suffix.lower() != ".mldsl":
                src_path = src_path.with_suffix(".mldsl")
            if not src_path.exists():
                warn(f"import не найден: {src_path}")
                continue

            out_lines.append(f"# [import] {src_path}")
            out_lines.extend(load_with_imports(src_path, stack))
            out_lines.append(f"# [/import] {src_path}")
        return out_lines

    # VS Code/PowerShell часто пишут UTF-8 с BOM; utf-8-sig убирает BOM автоматически.
    lines = load_with_imports(path, [])
    entries: list[dict] = []

    in_block = False
    current_kind = None  # event|func|loop
    current_name = None
    current_loop_ticks = None
    current_actions: list[tuple[str, str, str]] = []
    block_stack: list[str] = []  # nested blocks inside event/func/loop (e.g. if)
    declared_funcs: set[str] = set()
    MAX_ACTIONS_WARN = 43

    def flush_block():
        nonlocal current_kind, current_name, current_loop_ticks, current_actions
        if not current_kind:
            return

        if len(current_actions) >= MAX_ACTIONS_WARN:
            kind = current_kind
            nm = current_name or ""
            warn(f"строка `{kind}({nm})`: достигнуто {len(current_actions)} действий; возможно придётся разбивать на несколько строк/функций")

        if current_kind == "event":
            ev_name = event_variant_to_name(current_name or "")
            entries.append({"block": "diamond_block", "name": ev_name, "args": "no"})
        elif current_kind == "func":
            entries.append({"block": "lapis_block", "name": (current_name or ""), "args": "no"})
        elif current_kind == "loop":
            ticks = int(current_loop_ticks or 5)
            ticks = max(5, ticks)
            entries.append({"block": "emerald_block", "name": (current_name or ""), "args": str(ticks)})
        else:
            raise ValueError(f"Unknown block kind: {current_kind}")

        for block, name, args in current_actions:
            entries.append({"block": block, "name": name, "args": (args or "no")})

        current_kind = None
        current_name = None
        current_loop_ticks = None
        current_actions = []

    def begin_new_row():
        # split rows by inserting a newline marker between blocks
        if entries:
            entries.append({"block": "newline"})

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Close nested blocks first (so } inside event/func doesn't flush the whole outer block).
        if line == "}" and block_stack:
            block_stack.pop()
            # Exit the server-side piston bracket by advancing the code cursor without placing anything.
            # (Using "air" as a pause causes some servers to desync/teleport the player.)
            current_actions.append(("skip", "", "no"))
            continue

        m_ifp = IFPLAYER_RE.match(line)
        if m_ifp:
            if not in_block:
                raise ValueError("if_player must be inside event/func/loop block")
            block_stack.append("if")
            func = (m_ifp.group(1) or "").strip()
            arg_str = m_ifp.group(2) or ""
            res = compile_line(api, f"if_player.{func}({arg_str})")
            if not res:
                raise ValueError(f"Unknown if_player condition: {func}")
            pieces, spec = res
            sign1 = strip_colors(spec.get("sign1", "")).strip()
            sign2 = spec_menu_name(spec)
            menu = strip_colors(spec.get("menu", "")).strip()
            sign1_norm = norm_key(sign1)
            if sign1_norm in sign1_aliases:
                sign1_norm = norm_key(sign1_aliases[sign1_norm])
            block = blocks.get(sign1_norm)
            if not block:
                raise ValueError(
                    f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                )
            block_tok = block.replace("minecraft:", "")
            # For plan: embed metadata for skip-matching.
            # name: menu||expectedSign2
            expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
            StringName = sign2
            if expected_sign2:
                StringName = f"{(menu or sign2)}||{expected_sign2}"
            current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_select_ifp = SELECTOBJECT_IFPLAYER_RE.match(line)
        if m_select_ifp:
            if not in_block:
                raise ValueError("SelectObject.player.IfPlayer must be inside event/func/loop block")
            block_stack.append("if")
            func = (m_select_ifp.group(1) or "").strip()
            # Convert to lowercase for api lookup
            func_lower = func.lower()
            res = compile_line(api, f"if_player.{func_lower}()")
            if not res:
                raise ValueError(f"Unknown if_player condition: {func}")
            pieces, spec = res
            sign1 = strip_colors(spec.get("sign1", "")).strip()
            sign2 = spec_menu_name(spec)
            menu = strip_colors(spec.get("menu", "")).strip()
            sign1_norm = norm_key(sign1)
            if sign1_norm in sign1_aliases:
                sign1_norm = norm_key(sign1_aliases[sign1_norm])
            block = blocks.get(sign1_norm)
            if not block:
                raise ValueError(
                    f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                )
            block_tok = block.replace("minecraft:", "")
            # For plan: embed metadata for skip-matching.
            # name: menu||expectedSign2
            expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
            StringName = sign2
            if expected_sign2:
                StringName = f"{(menu or sign2)}||{expected_sign2}"
            current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_ifgame = IFGAME_RE.match(line)
        if m_ifgame:
            if not in_block:
                raise ValueError("if_game must be inside event/func/loop block")
            block_stack.append("if")
            func = (m_ifgame.group(1) or "").strip()
            arg_str = m_ifgame.group(2) or ""
            res = compile_line(api, f"if_game.{func}({arg_str})")
            if not res:
                raise ValueError(f"Unknown if_game condition: {func}")
            pieces, spec = res
            sign1 = strip_colors(spec.get("sign1", "")).strip()
            sign2 = spec_menu_name(spec)
            menu = strip_colors(spec.get("menu", "")).strip()
            sign1_norm = norm_key(sign1)
            if sign1_norm in sign1_aliases:
                sign1_norm = norm_key(sign1_aliases[sign1_norm])
            block = blocks.get(sign1_norm)
            if not block:
                raise ValueError(
                    f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                )
            block_tok = block.replace("minecraft:", "")
            # For plan: embed metadata for skip-matching.
            # name: menu||expectedSign2
            expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
            StringName = sign2
            if expected_sign2:
                StringName = f"{(menu or sign2)}||{expected_sign2}"
            current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_ifgame_old = IFGAME_OLD_RE.match(line)
        if m_ifgame_old:
            if not in_block:
                raise ValueError("IfGame must be inside event/func/loop block")
            block_stack.append("if")
            func = (m_ifgame_old.group(1) or "").strip()
            # Convert to lowercase for api lookup
            func_lower = func.lower()
            res = compile_line(api, f"if_game.{func_lower}()")
            if not res:
                raise ValueError(f"Unknown if_game condition: {func}")
            pieces, spec = res
            sign1 = strip_colors(spec.get("sign1", "")).strip()
            sign2 = spec_menu_name(spec)
            menu = strip_colors(spec.get("menu", "")).strip()
            sign1_norm = norm_key(sign1)
            if sign1_norm in sign1_aliases:
                sign1_norm = norm_key(sign1_aliases[sign1_norm])
            block = blocks.get(sign1_norm)
            if not block:
                raise ValueError(
                    f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                )
            block_tok = block.replace("minecraft:", "")
            # For plan: embed metadata for skip-matching.
            # name: menu||expectedSign2
            expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
            StringName = sign2
            if expected_sign2:
                StringName = f"{(menu or sign2)}||{expected_sign2}"
            current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_ifexists = IFEXISTS_RE.match(line)
        if m_ifexists:
            if not in_block:
                raise ValueError("ifexists must be inside event/func/loop block")
            block_stack.append("if")
            v = (m_ifexists.group(1) or m_ifexists.group(2) or "").strip()
            res = compile_line(api, f"if_value.var(var=var({v}))")
            pieces, spec = res
            sign1 = strip_colors(spec.get("sign1", "")).strip()
            sign2 = spec_menu_name(spec)
            menu = strip_colors(spec.get("menu", "")).strip()
            sign1_norm = norm_key(sign1)
            if sign1_norm in sign1_aliases:
                sign1_norm = norm_key(sign1_aliases[sign1_norm])
            block = blocks.get(sign1_norm)
            if not block:
                raise ValueError(
                    f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                )
            block_tok = block.replace("minecraft:", "")
            expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
            StringName = sign2
            if expected_sign2:
                StringName = f"{(menu or sign2)}||{expected_sign2}"
            current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_ift = IFTEXT_RE.match(line)
        if m_ift:
            if not in_block:
                raise ValueError("iftext must be inside event/func/loop block")
            block_stack.append("if")
            for res in compile_iftext_condition(api, m_ift.group(1)):
                pieces, spec = res
                sign1 = strip_colors(spec.get("sign1", "")).strip()
                sign2 = spec_menu_name(spec)
                menu = strip_colors(spec.get("menu", "")).strip()
                sign1_norm = norm_key(sign1)
                if sign1_norm in sign1_aliases:
                    sign1_norm = norm_key(sign1_aliases[sign1_norm])
                block = blocks.get(sign1_norm)
                if not block:
                    raise ValueError(
                        f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                    )
                block_tok = block.replace("minecraft:", "")
                expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
                StringName = sign2
                if expected_sign2:
                    StringName = f"{(menu or sign2)}||{expected_sign2}"
                current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_if = IF_RE.match(line)
        if m_if:
            if not in_block:
                raise ValueError("if must be inside event/func/loop block")
            block_stack.append("if")
            for res in compile_if_condition(api, m_if.group(1)):
                pieces, spec = res
                sign1 = strip_colors(spec.get("sign1", "")).strip()
                sign2 = spec_menu_name(spec)
                menu = strip_colors(spec.get("menu", "")).strip()
                sign1_norm = norm_key(sign1)
                if sign1_norm in sign1_aliases:
                    sign1_norm = norm_key(sign1_aliases[sign1_norm])
                block = blocks.get(sign1_norm)
                if not block:
                    raise ValueError(
                        f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                    )
                block_tok = block.replace("minecraft:", "")
                expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
                StringName = sign2
                if expected_sign2:
                    StringName = f"{(menu or sign2)}||{expected_sign2}"
                current_actions.append((block_tok, StringName, ",".join(pieces) if pieces else "no"))
            continue

        m_ev = EVENT_RE.match(line)
        if m_ev:
            flush_block()
            begin_new_row()
            current_kind = "event"
            current_name = m_ev.group(1)
            in_block = True
            continue
        m_fn = FUNC_RE.match(line)
        if m_fn:
            flush_block()
            begin_new_row()
            current_kind = "func"
            current_name = m_fn.group(1)
            if current_name:
                declared_funcs.add(str(current_name))
            in_block = True
            continue
        m_lp = LOOP_RE.match(line)
        if m_lp:
            flush_block()
            begin_new_row()
            current_kind = "loop"
            current_name = m_lp.group(1)
            current_loop_ticks = int(m_lp.group(2))
            in_block = True
            continue
        if line == "}":
            in_block = False
            flush_block()
            continue
        if not in_block:
            continue

        builtins = compile_builtin(api, line)
        if builtins:
            for pieces, spec in builtins:
                args_str = ",".join(pieces)
                # Warn on calling a function that is not declared in this file.
                if strip_colors(spec.get("sign2", "")).strip() in ("Вызвать функцию", "call_function"):
                    m_call = re.search(r"slot\(13\)=text\(([^)]+)\)", args_str)
                    if m_call:
                        fn_name = m_call.group(1).strip().strip('"').strip("'")
                        if fn_name and fn_name not in declared_funcs:
                            warn(f"строка {line_no}: вызов функции `{fn_name}()` не найден в этом файле (если это функция мира — можно игнорировать)")
                sign1 = strip_colors(spec.get("sign1", "")).strip()
                sign2 = spec_menu_name(spec)
                menu = strip_colors(spec.get("menu", "")).strip()
                sign1_norm = norm_key(sign1)
                if sign1_norm in sign1_aliases:
                    sign1_norm = norm_key(sign1_aliases[sign1_norm])
                block = blocks.get(sign1_norm)
                if not block:
                    raise ValueError(
                        f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json"
                    )
                block_tok = block.replace("minecraft:", "")
                expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
                StringName = sign2
                if expected_sign2:
                    StringName = f"{(menu or sign2)}||{expected_sign2}"
                current_actions.append((block_tok, StringName, args_str))
            continue

        res = compile_line(api, line)
        if not res:
            continue
        pieces, spec = res
        args_str = ",".join(pieces)

        sign1 = strip_colors(spec.get("sign1", "")).strip()
        sign2 = spec_menu_name(spec)
        menu = strip_colors(spec.get("menu", "")).strip()
        sign1_norm = norm_key(sign1)
        # apply alias if needed
        if sign1_norm in sign1_aliases:
            sign1_norm = norm_key(sign1_aliases[sign1_norm])
        block = blocks.get(sign1_norm)
        if not block:
            raise ValueError(f"Unknown block for sign1='{sign1}' (norm='{sign1_norm}'). Add to allactions.txt or Aliases.json")
        # PlaceModule accepts blockTok without minecraft: prefix too, but keep raw path
        block_tok = block.replace("minecraft:", "")
        expected_sign2 = strip_colors(spec.get("sign2", "")).strip() or strip_colors(spec.get("gui", "")).strip()
        StringName = sign2
        if expected_sign2:
            StringName = f"{(menu or sign2)}||{expected_sign2}"
        current_actions.append((block_tok, StringName, args_str))

    flush_block()
    return entries

def compile_commands(path: Path) -> list[str]:
    entries = compile_entries(path)
    out: list[str] = []
    i = 0
    while i < len(entries):
        e = entries[i]
        # each event starts a new /placeadvanced command; we emit one command per event block for now
        if e.get("block") != "diamond_block":
            i += 1
            continue
        event_name = e.get("name") or ""
        actions: list[tuple[str, str, str]] = []
        i += 1
        while i < len(entries) and entries[i].get("block") != "diamond_block":
            a = entries[i]
            actions.append((a.get("block") or "", a.get("name") or "", "no" if a.get("args") == "no" else (a.get("args") or "")))
            i += 1
        cmd = build_placeadvanced_command(event_block="diamond_block", event_name=event_name, actions=actions)
        if len(cmd) > MAX_CMD_LEN:
            raise ValueError(f"/placeadvanced too long: {len(cmd)} > {MAX_CMD_LEN} chars")
        out.append(cmd)
    return out

def main():
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("file", help="Path to .mldsl file")
    ap.add_argument("--plan", dest="plan_path", default=None, help="Write plan.json (entries format) to this path")
    ap.add_argument("--print-plan", action="store_true", help="Print plan.json (entries format) to stdout")
    args = ap.parse_args()

    src = Path(args.file)

    if args.plan_path or args.print_plan:
        entries = compile_entries(src)
        plan = {"entries": entries}
        if args.plan_path:
            out_path = Path(args.plan_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.print_plan:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    cmds = compile_commands(src)
    for c in cmds:
        print(c)


if __name__ == "__main__":
    main()
