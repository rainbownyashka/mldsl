import json
import re
import argparse
import ast
from pathlib import Path

from mldsl_paths import (
    actions_catalog_path,
    aliases_json_path,
    api_aliases_path,
    allactions_txt_path,
    ensure_dirs,
    gamevalues_path,
)

API_PATH = api_aliases_path()
ALIASES_PATH = aliases_json_path()
ALLACTIONS_PATH = allactions_txt_path()
GAMEVALUES_PATH = gamevalues_path()
MAX_CMD_LEN = 240

# Internal stacks for function args/returns. Names must be rare to avoid clashing with user variables in the world.
ARGS_STACK_NAME = "__mldsl_args"
RET_STACK_NAME = "__mldsl_ret"
TMP_VAR_PREFIX = "__mldsl_tmp"

# Stack top index. Your server's array GUI actions are 1-based.
STACK_TOP_INDEX = 1


def parse_item_display_name(raw: str) -> str:
    if not raw:
        return ""
    s = strip_colors(raw)
    if "]" in s:
        s = s.split("]", 1)[1]
    s = s.strip()
    if "|" in s:
        s = s.split("|", 1)[0].strip()
    return s


def load_known_events() -> dict:
    """
    Returns: norm(menu|sign2) -> (block, menuName, expectedSign2)
    - menuName: clickable GUI item title
    - expectedSign2: sign text used for skip-check
    """
    p = actions_catalog_path()
    if not p.exists():
        return {}
    try:
        catalog = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(catalog, list):
        return {}

    out = {}
    for rec in catalog:
        if not isinstance(rec, dict):
            continue
        signs = rec.get("signs") or ["", "", "", ""]
        sign1 = strip_colors(signs[0]).strip()
        sign2 = strip_colors(signs[1]).strip()
        s1 = sign1.lower()
        if "событие" not in s1:
            continue
        if "игрока" in s1:
            block = "diamond_block"
        elif "мира" in s1:
            block = "gold_block"
        else:
            continue
        menu = parse_item_display_name(rec.get("subitem") or rec.get("category") or "") or sign2
        if not menu:
            continue
        payload = (block, menu, sign2 or menu)
        out.setdefault(norm_key(menu), payload)
        if sign2:
            out.setdefault(norm_key(sign2), payload)
    return out


def load_api():
    ensure_dirs()
    if not API_PATH.exists():
        raise FileNotFoundError(
            f"Не найден API файл: {API_PATH}\n"
            "Сначала сгенерируй `out/` (api_aliases.json + docs), например:\n"
            "  python tools/build_all.py\n"
            "Или укажи MLDSL_DATA_DIR/MLDSL_PORTABLE если используешь portable установку."
        )
    return json.loads(API_PATH.read_text(encoding="utf-8"))

_gamevalues_cache = None


def load_gamevalues() -> dict:
    global _gamevalues_cache
    if _gamevalues_cache is not None:
        return _gamevalues_cache
    if not GAMEVALUES_PATH.exists():
        _gamevalues_cache = {}
        return _gamevalues_cache
    try:
        _gamevalues_cache = json.loads(GAMEVALUES_PATH.read_text(encoding="utf-8"))
    except Exception:
        _gamevalues_cache = {}
    return _gamevalues_cache


def resolve_gamevalue_token(token: str) -> str | None:
    """
    Resolves gamevalue tokens to LocName. Supports:
    - gamevalue.CURRENT_HEALTH
    - gamevalue.Текущее_здоровье (uses out/gamevalues.json byKey)
    - gamevalue("CURRENT_HEALTH") / gamevalue("Текущее здоровье")
    - яблоко.<...> / игровое_значение.<...> / gameval.<...>
    Returns LocName or None.
    """
    s = (token or "").strip()
    if not s:
        return None
    prefixes = (
        "gamevalue",
        "gameval",
        "gamevalue",
        "apple",
        "яблоко",
        "игровое_значение",
        "игровоезначение",
        "gamevalue",
    )

    m_call = re.match(r"^([a-zA-Z_\u0400-\u04FF]+)\s*\(\s*(.+?)\s*\)\s*$", s)
    if m_call:
        head = (m_call.group(1) or "").strip().lower()
        inner = (m_call.group(2) or "").strip()
        if head in prefixes:
            if (inner.startswith('"') and inner.endswith('"')) or (inner.startswith("'") and inner.endswith("'")):
                inner = inner[1:-1]
            s = inner
        else:
            return None
    else:
        m_dot = re.match(r"^([a-zA-Z_\u0400-\u04FF]+)\.(.+)$", s)
        if m_dot:
            head = (m_dot.group(1) or "").strip().lower()
            if head not in prefixes:
                return None
            # allow gamevalue.category.value -> take last segment
            s = (m_dot.group(2) or "").split(".")[-1].strip()
        else:
            return None

    # direct LocName
    if re.match(r"^[A-Z0-9_]+$", s):
        return s

    # lookup by human name
    gv = load_gamevalues()
    by_key = gv.get("byKey") if isinstance(gv, dict) else None
    if isinstance(by_key, dict):
        key = norm_key(s)
        loc = by_key.get(key)
        if isinstance(loc, str) and loc:
            return loc
    return None


def maybe_wrap_gamevalue(token: str) -> str | None:
    loc = resolve_gamevalue_token(token)
    if loc:
        return f"apple({loc})"
    return None


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
    # module aliases (keep in sync with extension.js)
    module_aliases = {
        "игрок": "player",
        "player": "player",
        "событие": "event",
        "event": "event",
        "select": "select",
        "выборка": "select",
    }
    orig_module = module
    module = module_aliases.get(module, module)
    # Backward compatibility: older alias catalogs used misc.* for select actions.
    if module == "select" and not api.get("select") and api.get("misc"):
        module = "misc"
    mod = api.get(module)
    if module == "misc" and (func or "").startswith("vybrat_") and api.get("select"):
        sel_mod = api.get("select") or {}
        if func in sel_mod:
            return func, sel_mod[func]
        for canon, spec in sel_mod.items():
            aliases = spec.get("aliases") or []
            if func in aliases:
                return canon, spec
    if not mod:
        return None, None
    if orig_module in ("select", "выборка"):
        key = re.sub(r"[_\\s]+", "", (func or "").strip().lower())
        select_sh = {
            "allplayers": "vse_igroki",
            "allplayer": "vse_igroki",
            "allmobs": "vse_moby",
            "allentities": "vse_suschnosti",
            "randomplayer": "sluchaynyy_igrok",
            "randommob": "sluchaynyy_mob",
            "randentity": "sluchaynaya_suschnost",
            "randomentity": "sluchaynaya_suschnost",
            "defaultplayer": "igrok_po_umolchaniyu",
            "defaultentity": "suschnost_po_umolchaniyu",
        }
        func = select_sh.get(key, func)
    # direct name
    if func in mod:
        return func, mod[func]
    # alias match
    for canon, spec in mod.items():
        aliases = spec.get("aliases") or []
        if func in aliases:
            return canon, spec
    return None, None

def split_args(arg_str: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    in_str = False
    str_ch = ""
    esc = False
    paren = 0
    brace = 0
    bracket = 0
    for ch in arg_str:
        if esc:
            buf += ch
            esc = False
            continue
        if ch == "\\":
            esc = True
            buf += ch
            continue
        if ch in ('"', "'"):
            if in_str and ch == str_ch:
                in_str = False
                str_ch = ""
            elif not in_str:
                in_str = True
                str_ch = ch
            buf += ch
            continue
        if not in_str:
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace = max(0, brace - 1)
            elif ch == "[":
                bracket += 1
            elif ch == "]":
                bracket = max(0, bracket - 1)

        if ch == "," and not in_str and paren == 0 and brace == 0 and bracket == 0:
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

    def split_top_level_eq(token: str) -> tuple[str, str] | None:
        s = token or ""
        in_str = False
        str_ch = ""
        esc = False
        paren = brace = bracket = 0
        for i, ch in enumerate(s):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch in ('"', "'"):
                if in_str and ch == str_ch:
                    in_str = False
                    str_ch = ""
                elif not in_str:
                    in_str = True
                    str_ch = ch
                continue
            if in_str:
                continue
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace = max(0, brace - 1)
            elif ch == "[":
                bracket += 1
            elif ch == "]":
                bracket = max(0, bracket - 1)
            elif ch == "=" and paren == 0 and brace == 0 and bracket == 0:
                return s[:i], s[i + 1 :]
        return None

    for p in split_args(arg_str):
        # If the whole token is quoted, it's always positional (it may contain '=' inside).
        ps = p.strip()
        if len(ps) >= 2 and ((ps.startswith('"') and ps.endswith('"')) or (ps.startswith("'") and ps.endswith("'"))):
            pos.append(ps[1:-1])
            continue
        eq = split_top_level_eq(p)
        if eq is not None:
            k, v = eq
            v = v.strip()
            # Keep explicit quotes so downstream mode wrappers can distinguish
            # literal text from bare identifiers (e.g. TEXT sugar).
            kv[k.strip()] = v
        else:
            v = p.strip()
            # Keep explicit quotes for positional args as well.
            pos.append(v)
    return kv, pos

def ru_to_translit_ident(s: str) -> str:
    """
    Best-effort RU -> translit conversion for identifiers (enum/param names).
    Supports writing keyword args in Cyrillic, e.g. режим_игры=... for rezhim_igry.
    """
    if not s:
        return ""
    m = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ь": "",
        "ъ": "",
    }
    out = []
    for ch in str(s):
        lo = ch.lower()
        if lo in m:
            tr = m[lo]
            out.append(tr.upper() if ch.isupper() else tr)
        else:
            out.append(ch)
    return "".join(out)

def wrap_value(mode: str | None, value: str) -> str:
    v = (value or "").strip()
    if not v:
        return v
    gv = maybe_wrap_gamevalue(v)
    if gv:
        return gv
    # Keep only known wrapper forms; everything else that looks like a call is NOT executable on server.
    m_wrap = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(.*\)\s*$", v)
    if m_wrap:
        head = (m_wrap.group(1) or "").lower()
        allowed = {
            "text",
            "num",
            "var",
            "var_save",
            "arr",
            "arr_save",
            "array",
            "loc",
            "apple",
            "gamevalue",
            "gameval",
            "игровое_значение",
            "яблоко",
            "item",
        }
        if head in allowed:
            return v
    # Prevent accidental "nested calls" being treated as plain text/number/etc.
    # If user really wants the literal text `foo()` they should quote it.
    if re.match(r"^[\w\u0400-\u04FF]+(?:\.[\w\u0400-\u04FF]+)?\s*\(.*\)\s*$", v):
        raise ValueError(
            f"Вложенный вызов `{v}` в аргументе не выполняется на сервере автоматически. "
            "Сделай так: tmp = foo(); и используй %var(tmp)% в тексте, или передай строку в кавычках."
        )
    m = (mode or "").upper()
    if m == "TEXT":
        # Sugar: bare identifiers in TEXT slots are treated as variable references.
        # Use quotes or explicit text(...) to force literal text.
        if re.match(rf"^{NAME_RE}$", v) and safe_eval_number_expr(v) is None:
            return f"var({v})"
        return f"text({v})"
    if m == "NUMBER":
        return f"num({v})"
    if m == "VARIABLE":
        return f"var({v})"
    if m == "LOCATION":
        return f"loc({v})"
    if m == "ARRAY":
        return f"arr({v})"
    if m == "ITEM":
        return f"item({v})"
    return v


# Identifiers:
# - allow %placeholders% inside variable names (e.g. %selected%counter)
# - keep calls/modules stricter for now (no % in module/function names)
NAME_RE = r"[%%\w\u0400-\u04FF]+"
CALL_RE = re.compile(r"^\s*([\w\u0400-\u04FF]+)\.([\w\u0400-\u04FF]+)\s*\((.*)\)\s*;?\s*$")
# event(<name>) { ... } and empty event() { ... }
# - allow spaces in names (e.g. "Событие чата")
# - allow quotes: event("Правый клик")
EVENT_RE = re.compile(r'^\s*event\s*\(\s*(?:"([^"]*)"|([^)]*?))\s*\)\s*\{\s*$', re.I)
BARE_CALL_RE = re.compile(r"^\s*([\w\u0400-\u04FF]+)\s*\((.*)\)\s*;?\s*$")
FUNC_RE = re.compile(
    rf"^\s*(?:func|function|def|функция)\s*(?:\(\s*)?([\w\u0400-\u04FF]+)(?:\s*\))?(?:\s*\(\s*([^\)]*)\s*\))?\s*\{{\s*$",
    re.I,
)
VFUNC_RE = re.compile(
    rf"^\s*(?:vfunc|vfunction|вирт_функция)\s+([\w\u0400-\u04FF]+)\s*\(\s*([^\)]*)\s*\)\s*$",
    re.I,
)
LOOP_RE = re.compile(rf"^\s*(?:loop|цикл)\s+([\w\u0400-\u04FF]+)(?:\s+every)?\s+(\d+)\s*\{{\s*$", re.I)
ASSIGN_RE = re.compile(
    rf"^\s*(?:(save)\s+)?({NAME_RE})\s*(?:~\s*)?(?:([+\-*/])\s*)?=\s*(.+?)\s*;?\s*$",
    re.I,
)
SAVE_SHORTHAND_RE = re.compile(rf"^\s*({NAME_RE})\s*~\s*(.+?)\s*;?\s*$", re.I)
IMPORT_RE = re.compile(r"^\s*(?:import|use|использовать)\s+([^\s;#]+)\s*;?\s*$", re.I)

IFPLAYER_RE = re.compile(r"^\s*if_?player\.([\w\u0400-\u04FF]+)(?:\s*\((.*)\))?\s*\{\s*$", re.I)
SELECTOBJECT_IFPLAYER_RE = re.compile(r"^\s*SelectObject\.player\.IfPlayer\.([\w\u0400-\u04FF]+)\s*\{\s*$", re.I)
IFGAME_RE = re.compile(r"^\s*if_?game\.([\w\u0400-\u04FF]+)(?:\s*\((.*)\))?\s*\{\s*$", re.I)
IFGAME_OLD_RE = re.compile(r"^\s*IfGame\.([\w\u0400-\u04FF]+)\s*\{\s*$", re.I)
IF_RE = re.compile(r"^\s*if\s+(.+?)\s*\{\s*$", re.I)
IFTEXT_RE = re.compile(r"^\s*iftext\s+(.+?)\s*\{\s*$", re.I)
IFEXISTS_RE = re.compile(rf"^\s*ifexists\s*(?:\(\s*({NAME_RE})\s*\)|\s+({NAME_RE}))\s*\{{\s*$", re.I)
SELECT_RE = re.compile(
    r"^\s*select\.([\w\u0400-\u04FF]+(?:\.[\w\u0400-\u04FF]+)*)\s*(?:\(\s*(.*?)\s*\))?\s*(\{)?\s*$",
    re.I,
)


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
    # Pseudo actions for empty-sign blocks from exportcode translator.
    # They preserve flow/brace semantics and compile to valid plan blocks
    # with empty action name and no args.
    if (func or "").strip().lower() == "noaction":
        mod = (module or "").strip().lower()
        if mod == "player":
            return ([], {"sign1": "Действие игрока", "sign2": "", "menu": "", "gui": ""})
        if mod == "game":
            return ([], {"sign1": "Действие игры", "sign2": "", "menu": "", "gui": ""})
        if mod == "if_player":
            return ([], {"sign1": "Если игрок", "sign2": "", "menu": "", "gui": ""})
        if mod == "if_game":
            return ([], {"sign1": "Если игра", "sign2": "", "menu": "", "gui": ""})
        if mod == "if_value":
            return ([], {"sign1": "Если переменная", "sign2": "", "menu": "", "gui": ""})
        raise ValueError(f"Unknown noaction module: {module}")
    canon, spec = find_action(api, module, func)
    if not spec:
        raise ValueError(f"Unknown action: {module}.{func}")

    kv, pos = parse_call_args(arg_str)

    # Accept Cyrillic keyword names for params/enums by transliterating to canonical keys.
    # Example: if_player.режим_игрока(режим_игры="Креатив")
    extra_kv: dict[str, str] = {}
    for k, v in (kv or {}).items():
        if any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in str(k)):
            kk = ru_to_translit_ident(str(k))
            if kk and kk not in kv and kk not in extra_kv:
                extra_kv[kk] = v
    if extra_kv:
        kv.update(extra_kv)
    # Special-case: some actions use a plain chest without any glass "arg markers".
    # For such actions, we still want to support passing items via slot(N)=item(...)
    # so /placeadvanced can fill the chest.
    def _wrap_item_token(tok: str) -> str:
        s = (tok or "").strip()
        if not s:
            return s
        if re.match(r"^item\s*\(.*\)\s*$", s, re.I):
            return s
        # allow raw item ids like stone / minecraft:stone / "stone"
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        return f"item({s})"

    pieces = []
    params = spec.get("params") or []

    def _is_fill_region_action(_module: str, _spec: dict) -> bool:
        if (_module or "").strip().lower() != "game":
            return False
        s2 = strip_colors(_spec.get("sign2", "")).strip().lower()
        return s2 == "заполнить область"

    # Action sugar: "Заполнить область" (fill region with blocks)
    # API param list is usually: value(ANY), loc(LOCATION), loc2(LOCATION), num(NUMBER)
    # In practice, `value` is a block item placed into the yellow "item/block" glass slot.
    if _is_fill_region_action(module, spec):
        # Allow friendlier keyword aliases for the block argument.
        if "value" not in kv:
            for k in ("block", "blok", "блок", "block_id", "id", "item", "предмет"):
                if k in kv and kv[k]:
                    kv["value"] = kv[k]
                    break

    # Heuristic: "Выдать предметы" takes items from a chest, but the GUI has no marker glass.
    # Allow: player.выдать_предметы(item(stone), количество=3) -> slot(0)=item(stone,count=3)
    if not params:
        s1 = strip_colors(spec.get("sign1", "")).strip().lower()
        s2 = strip_colors(spec.get("sign2", "")).strip().lower()
        if s1 == "действие игрока" and s2 == "выдать предметы":
            count_kw = kv.get("количество") or kv.get("count") or kv.get("amount")
            items = []
            # Positional tokens are treated as items.
            for t in pos or []:
                items.append(_wrap_item_token(t))
            # Also allow explicit named parameter.
            for k in ("item", "items", "предмет", "предметы"):
                if k in kv and kv[k]:
                    items.append(_wrap_item_token(kv[k]))
            if count_kw is not None:
                raise ValueError(
                    "Выдать предметы: параметр `количество` больше не поддерживается. "
                    "Указывай количество внутри `item(...)`, например: item(stone, count=3)."
                )
            if items:
                for idx, it in enumerate(items):
                    if not it:
                        continue
                    pieces.append(f"slot({idx})={it}")

    # positional args fill params in order
    if pos:
        for idx, raw in enumerate(pos):
            if idx >= len(params):
                break
            pname = params[idx]["name"]
            if pname not in kv:
                kv[pname] = raw

    # Compatibility sugar: this action is often used as a single-variable existence check.
    # If only one variable is passed, mirror it to var2.
    if (module or "").strip().lower() == "if_value" and canon == "peremennaya_suschestvuet":
        if "var" in kv and "var2" not in kv:
            kv["var2"] = kv["var"]

    for p in params:
        name = p["name"]
        if name not in kv:
            continue
        # Special-case: fill-region expects a block item in ANY slot; wrap raw ids to item(...)
        if _is_fill_region_action(module, spec) and (name == "value" or p.get("slot") == 13):
            val = _wrap_item_token(kv[name])
        else:
            val = wrap_value(p.get("mode"), kv[name])
        pieces.append(f"slot({p['slot']})={val}")

    def _unquote_preserve_spaces(v: str) -> str:
        s = "" if v is None else str(v)
        s = s.strip()
        if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
            return s[1:-1]
        return s

    def _norm_enum_value(v: str) -> str:
        # ignore spaces/punctuation/case for matching; keep RU letters
        s = strip_colors(v or "").casefold()
        s = s.replace("ё", "е")
        s = re.sub(r"[\s_\\-]+", "", s)
        s = re.sub(r"[\"'`]+", "", s)
        s = re.sub(r"[.,:;()\\[\\]{}<>|]+", "", s)
        return s

    def _resolve_separator_shorthand(raw_val: str, opts: dict[str, int]) -> int | None:
        # Common server enums: no separator / space / newline.
        # Accept human shorthands: "", " ", "\\n", "newline", "пробел", "новая строка", etc.
        def find_by_contains(*needles: str) -> int | None:
            norm_needles = [_norm_enum_value(n) for n in needles if n is not None]
            for k, c in opts.items():
                nk = _norm_enum_value(k)
                if all(n in nk for n in norm_needles):
                    return c
            return None

        rv = "" if raw_val is None else str(raw_val)
        rv_norm = _norm_enum_value(rv)

        # space
        if rv == " " or rv_norm in ("space", "пробел", "разделениепробелом"):
            v = find_by_contains("пробел")
            if v is not None:
                return v
            return find_by_contains("space")

        # newline
        if rv in ("\\n", "\n") or rv_norm in (
            "newline",
            "new_line",
            "line",
            "строка",
            "новаястрока",
            "разделениеновойстрокой",
        ):
            v = find_by_contains("нов", "строк")
            if v is not None:
                return v
            v = find_by_contains("нов", "строч")
            if v is not None:
                return v
            v = find_by_contains("перенос", "строк")
            if v is not None:
                return v
            return find_by_contains("newline")

        # none / empty
        if rv_norm in ("", "none", "noseparator", "без", "безразделения"):
            v = find_by_contains("без", "раздел")
            if v is not None:
                return v
            v = find_by_contains("no", "separator")
            if v is not None:
                return v
            return 0 if opts else None

        return None

    # enum sugar: if key matches enum name, convert to clicks(slot,n)
    for e in spec.get("enums") or []:
        ename = e.get("name")
        if not ename or ename not in kv:
            continue
        raw_token = kv[ename]
        raw_val = _unquote_preserve_spaces(raw_token)
        opts = e.get("options") or {}

        clicks = None
        if isinstance(opts, dict) and opts:
            # exact
            if raw_val in opts:
                clicks = opts[raw_val]
            else:
                # separator shorthands: "", " ", "\n"
                clicks = _resolve_separator_shorthand(raw_val, opts)
                if clicks is None:
                    # fuzzy (ignore spaces/case)
                    import difflib

                    norm_map: dict[str, int] = {}
                    norm_to_key: dict[str, str] = {}
                    for k, v in opts.items():
                        nk = _norm_enum_value(k)
                        norm_map[nk] = v
                        norm_to_key[nk] = k

                    raw_norm = _norm_enum_value(raw_val)
                    clicks = norm_map.get(raw_norm)

                    # prefix/contains match (conservative): only if unique
                    if clicks is None and raw_norm and len(raw_norm) >= 4:
                        hits = [nk for nk in norm_map.keys() if nk.startswith(raw_norm) or raw_norm in nk]
                        if len(hits) == 1:
                            fixed = hits[0]
                            clicks = norm_map[fixed]
                            print(
                                f"[warn] enum `{ename}`: исправлено `{raw_val}` -> `{norm_to_key.get(fixed, fixed)}`",
                                file=__import__('sys').stderr,
                            )

                    # close match (still conservative). Use ratio + margin to avoid accidental wrong match.
                    if clicks is None and raw_norm and len(raw_norm) >= 4:
                        def ratio(a: str, b: str) -> float:
                            return difflib.SequenceMatcher(None, a, b).ratio()

                        scored = sorted(
                            ((ratio(raw_norm, nk), nk) for nk in norm_map.keys()),
                            key=lambda x: x[0],
                            reverse=True,
                        )
                        if scored:
                            best_r, best_k = scored[0]
                            second_r = scored[1][0] if len(scored) > 1 else 0.0
                            if best_r >= 0.88 and (best_r - second_r) >= 0.04:
                                clicks = norm_map[best_k]
                                print(
                                    f"[warn] enum `{ename}`: исправлено `{raw_val}` -> `{norm_to_key.get(best_k, best_k)}`",
                                    file=__import__('sys').stderr,
                                )
        if clicks is None:
            # allow numeric
            try:
                clicks = int(str(raw_val).strip())
            except Exception:
                examples = ", ".join(list(opts.keys())[:8]) if isinstance(opts, dict) else ""
                more = "..." if isinstance(opts, dict) and len(opts) > 8 else ""
                raise ValueError(
                    f"enum `{ename}`: неизвестное значение `{raw_val}`. Варианты: {examples}{more}"
                )

        # IMPORTANT: server already applies 1 click when you put the item; so "clicks(...,0)" is not safe.
        if int(clicks) > 0:
            pieces.append(f"clicks({e['slot']},{int(clicks)})=0")

    return pieces, spec

def compile_builtin(api: dict, line: str, func_sigs: dict[str, list[str]] | None = None, debug_stacks: bool = False):
    m = BARE_CALL_RE.match(line)
    if not m or "." in (m.group(1) or ""):
        # assignment sugar doesn't look like a call
        m_short = SAVE_SHORTHAND_RE.match(line)
        if m_short:
            name = (m_short.group(1) or "").strip()
            rhs = (m_short.group(2) or "").strip()
            # Don't treat `name~ = ...` as shorthand; that's regular assignment with "~" marker.
            if rhs.lstrip().startswith("="):
                m_short = None
            else:
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
        if save_kw == "save":
            saved = True
        # support `name~ = ...` and `name ~ = ...`
        if re.search(rf"^\s*(?:save\s+)?{re.escape(name)}\s*~", line, re.I):
            saved = True

        if not name or not rhs:
            return None

        def wrap_var_target(var_name: str, save_flag: bool) -> str:
            return f"var_save({var_name})" if save_flag else f"var({var_name})"

        def wrap_array_target(arr_name: str, save_flag: bool) -> str:
            return f"arr_save({arr_name})" if save_flag else f"arr({arr_name})"

        def wrap_any_value(token: str) -> str:
            s = (token or "").strip()
            if not s:
                return "text()"
            gv = maybe_wrap_gamevalue(s)
            if gv:
                return gv
            # keep explicit wrappers
            if re.match(r"^(?:text|num|var|var_save|arr|arr_save|loc|item|apple)\s*\(.*\)\s*$", s, re.I):
                return s
            # quoted string
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                inner = s[1:-1]
                return f"text({inner})"
            # numeric literal / expr (simple)
            vnum = safe_eval_number_expr(s)
            if vnum is not None:
                if abs(vnum - int(vnum)) < 1e-9:
                    return f"num({int(vnum)})"
                return f"num({vnum})"
            # fallback: treat as variable reference
            if re.match(rf"^{NAME_RE}$", s):
                return f"var({s})"
            return s

        def compile_push_args_stack(func_name: str, args: list[str]) -> list[tuple[list[str], dict]]:
            """
            Pushes args onto global mldsl args stack so nested calls don't overwrite each other.
            Layout: [argc, arg1, arg2, ...] at the front (index 1..).
            We implement by inserting argN..arg1 at index=1, then inserting argc at index=1.
            Returns synthetic actions as list of (pieces, spec).
            """
            if func_sigs and func_name in func_sigs:
                expected = len(func_sigs.get(func_name) or [])
                if expected != len(args):
                    raise ValueError(f"{func_name}(): ожидалось аргументов {expected}, получено {len(args)}")

            out = []
            # We treat the args stack as a stack with top at STACK_TOP_INDEX.
            # Insert args in reverse order so arg1 becomes the top element.
            for raw_arg in reversed(args):
                val = wrap_any_value(raw_arg)
                res = compile_line(
                    api,
                    f"array.vstavit_v_massiv(arr=arr({ARGS_STACK_NAME}), number=num({STACK_TOP_INDEX}), value={val})",
                )
                if not res:
                    raise ValueError("args: не найдено действие 'Вставить в массив'")
                out.append(res)
            if debug_stacks:
                res = compile_line(api, f"array.get_array_2(arr=arr({ARGS_STACK_NAME}), var=var({TMP_VAR_PREFIX}argslen))")
                if res:
                    out.append(res)
                res = compile_line(api, f'player.message("DBG args_len=%var({TMP_VAR_PREFIX}argslen)%")')
                if res:
                    out.append(res)
            return out

        # Array literal sugar:
        #   arr~ = [1, 2, "hello"]
        # Compiles into array.ochistit_sozdat_massiv(...) + array.add_array(...) in chunks.
        if rhs.startswith("[") and rhs.endswith("]"):
            inner = rhs[1:-1].strip()
            elems = split_args(inner) if inner else []
            wrapped = [wrap_any_value(e) for e in elems]
            out = []

            first_chunk = wrapped[:9]
            parts = [f"arr={wrap_array_target(name, saved)}"]
            for idx, val in enumerate(first_chunk, start=1):
                key = "value" if idx == 1 else f"value{idx}"
                parts.append(f"{key}={val}")

            res = compile_line(api, f"array.ochistit_sozdat_massiv({', '.join(parts)})")
            if not res:
                res = compile_line(api, f"array.sozdat_massiv({', '.join(parts)})")
            if not res:
                raise ValueError("array literal: не найдено действие 'Очистить/Создать массив'")
            out.append(res)

            rest = wrapped[9:]
            for i in range(0, len(rest), 9):
                chunk = rest[i:i + 9]
                parts = [f"arr={wrap_array_target(name, saved)}"]
                for idx, val in enumerate(chunk, start=1):
                    key = "value" if idx == 1 else f"value{idx}"
                    parts.append(f"{key}={val}")
                res = compile_line(api, f"array.add_array({', '.join(parts)})")
                if not res:
                    raise ValueError("array literal: не найдено действие 'Добавить в конец массива'")
                out.append(res)
            return out

        # Slice sugar for text: dst = src[3:5]
        m_slice = re.match(rf"^({NAME_RE}|\".*?\"|'.*?')\[(\d+)\s*:\s*(\d+)\]$", rhs)
        if m_slice:
            src = m_slice.group(1)
            start = int(m_slice.group(2))
            end = int(m_slice.group(3))
            if (src.startswith('"') and src.endswith('"')) or (src.startswith("'") and src.endswith("'")):
                src_text = f"text({src[1:-1]})"
            else:
                src_text = f"text(%var({src})%)"
            synthetic = f"var.text(var={wrap_var_target(name, saved)}, text={src_text}, num=num({start}), num2=num({end}))"
            res = compile_line(api, synthetic)
            if not res:
                raise ValueError("slice: не найдено действие 'Обрезать текст'")
            return [res]

        # Index sugar for array element: dst = arrName[2]
        m_idx = re.match(rf"^({NAME_RE})\[(\d+)\]$", rhs)
        if m_idx:
            src_arr = m_idx.group(1)
            idx = int(m_idx.group(2))
            synthetic = f"array.get_array(arr=arr({src_arr}), number=num({idx}), var={wrap_var_target(name, saved)})"
            res = compile_line(api, synthetic)
            if not res:
                raise ValueError("array index: не найдено действие 'Получить элемент массива'")
            return [res]

        # Function-return sugar (sync only):
        #   x = foo()
        # Compiles:
        #   call(foo)
        #   x = pop(mldsl ret stack)
        m_call_expr = re.match(rf"^(?:([\w\u0400-\u04FF]+)\.)?([\w\u0400-\u04FF]+)\s*\((.*)\)\s*$", rhs)
        if m_call_expr:
            fn = (m_call_expr.group(2) or "").strip()
            inside = (m_call_expr.group(3) or "").strip()
            reserved = {
                "event",
                "func",
                "function",
                "def",
                "loop",
                "цикл",
                "функция",
                "if",
                "iftext",
                "ifexists",
            }
            if fn and fn not in reserved:
                # positional args only for now
                if inside:
                    args = split_args(inside)
                else:
                    args = []
                out = []
                # push args (if any)
                if args:
                    out.extend(compile_push_args_stack(fn, args))
                # 1) call(func) (sync)
                spec_call = api.get("game", {}).get("call_function") or api.get("game", {}).get("вызвать_функцию")
                if not spec_call:
                    raise ValueError("Function call sugar failed: no call_function action in api")
                out.append(([f"slot(13)=text({fn})"], spec_call))
                if debug_stacks:
                    res = compile_line(api, f"array.get_array_2(arr=arr({RET_STACK_NAME}), var=var({TMP_VAR_PREFIX}retlen_before))")
                    if res:
                        out.append(res)
                    res = compile_line(api, f'player.message("DBG ret_len_before=%var({TMP_VAR_PREFIX}retlen_before)%")')
                    if res:
                        out.append(res)
                # 2) read ret from __ret[top] into target var
                target_var = wrap_var_target(name, saved)
                res = compile_line(
                    api, f"array.get_array(arr=arr({RET_STACK_NAME}), number=num({STACK_TOP_INDEX}), var={target_var})"
                )
                if not res:
                    raise ValueError("return/pop: не найдено действие 'Получить элемент массива'")
                out.append(res)
                # 3) pop __ret[top]
                res = compile_line(api, f"array.remove_array(arr=arr({RET_STACK_NAME}), number=num({STACK_TOP_INDEX}))")
                if not res:
                    raise ValueError("return/pop: не найдено действие 'Удалить элемент массива'")
                out.append(res)
                if debug_stacks:
                    res = compile_line(api, f"array.get_array_2(arr=arr({RET_STACK_NAME}), var=var({TMP_VAR_PREFIX}retlen_after))")
                    if res:
                        out.append(res)
                    res = compile_line(api, f'player.message("DBG ret_len_after=%var({TMP_VAR_PREFIX}retlen_after)%")')
                    if res:
                        out.append(res)
                return out

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

        var_token = wrap_var_target(name, saved)

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

        if op in {"+", "-", "*", "/"}:
            # Augmented assignment sugar: x += y, x -= y, x *= y, x /= y.
            aug_expr = f"{name} {op} ({rhs})"
            aug_expr_s, aug_map = preprocess_numeric_expr(aug_expr)
            try:
                aug_node = ast.parse(aug_expr_s, mode="eval").body
            except Exception:
                aug_node = None
            if not is_supported_numeric_expr_ast(aug_node):
                raise ValueError(f"assignment '{op}=' supports numeric expressions only: {rhs}")
            return compile_numeric_expression(api, target_var=var_token, expr_node=aug_node, name_map=aug_map)

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

        if kv:
            raise ValueError(f"{name}(): пока поддерживаются только позиционные аргументы (без key=value)")

        # positional args: push stack frame, then call
        out = []
        if pos:
            out.extend(compile_push_args_stack(name, pos))

        pieces = [f"slot(13)=text({name})"]
        if async_flag:
            pieces.append("clicks(16,1)=0")
        spec = api.get("game", {}).get("call_function")
        if not spec:
            # fallback older name
            spec = api.get("game", {}).get("вызвать_функцию")
        if not spec:
            raise ValueError("Function call sugar failed: no call_function action in api")
        out.append((pieces, spec))

        # As a statement-call, discard one return value to keep __ret clean.
        # (Every func gets an implicit return if it doesn't have explicit return.)
        if not async_flag:
            res = compile_line(api, f"array.remove_array(arr=arr({RET_STACK_NAME}), number=num({STACK_TOP_INDEX}))")
            if not res:
                raise ValueError("return/discard: не найдено действие 'Удалить элемент массива'")
            out.append(res)
        return out

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
        print(
            f"[warn] formula for {target_var} compiled into {len(flat)} actions (+{extra})",
            file=__import__('sys').stderr,
        )

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
    known_events = load_known_events()
    # Debug-only: can be wired to CLI later.
    debug_stacks = False

    def norm_ident(s: str) -> str:
        s = strip_colors(s or "").lower()
        s = re.sub(r"[\s_\\-]+", "", s)
        return s

    def compile_action_tuple(module: str, func: str, arg_str: str = "") -> tuple[str, str, str]:
        res = compile_line(api, f"{module}.{func}({arg_str})")
        if not res:
            raise ValueError(f"Unknown action: {module}.{func}")
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
        return (block_tok, StringName, ",".join(pieces) if pieces else "no"), spec

    # Selection (Выбрать объект) scoping:
    # `select.xxx { ... }` restores the previous selection on `}`.
    DEFAULT_SELECT_PLAYER, _ = compile_action_tuple("select", "vybrat_igroka_po_umolchaniyu")
    DEFAULT_SELECT_ENTITY, _ = compile_action_tuple("select", "vybrat_suschnost_po_umolchaniyu")
    current_select: tuple[str, str, str] | None = None
    select_stack: list[tuple[str, str, str] | None] = []
    select_default_stack: list[tuple[str, str, str]] = []

    def select_domain(spec: dict) -> str:
        blob = " ".join(
            [
                strip_colors(spec.get("sign2", "")).lower(),
                strip_colors(spec.get("gui", "")).lower(),
                strip_colors(spec.get("menu", "")).lower(),
            ]
        )
        if "игрок" in blob:
            return "player"
        if "моб" in blob or "сущност" in blob:
            return "entity"
        return "player"

    def find_select_action(chain: str) -> tuple[str, dict]:
        mod = api.get("select") or api.get("misc") or {}
        parts = [p for p in (chain or "").split(".") if p]
        leaf = parts[-1] if parts else ""
        if not leaf:
            raise ValueError("select: empty selector")

        leaf_key = norm_ident(leaf)
        leaf_syn = {
            # common user wording -> in-game menu wording
            "приседает": "kradetsya",
            "нашифте": "kradetsya",
            "шифт": "kradetsya",
            "sneak": "kradetsya",
            "sneaking": "kradetsya",
            "держит": "держит_предмет",
            "derzhit": "держит_предмет",
            "переменнаяравна": "значение_равно",
            "peremennayaravna": "znachenie_ravno",
        }
        leaf_key = leaf_syn.get(leaf_key, leaf_key)
        leaf_sh = {
            "allplayers": "vse_igroki",
            "allplayer": "vse_igroki",
            "allmobs": "vse_moby",
            "allentities": "vse_suschnosti",
            "randomplayer": "sluchaynyy_igrok",
            "randommob": "sluchaynyy_mob",
            "randentity": "sluchaynaya_suschnost",
            "randomentity": "sluchaynaya_suschnost",
            "defaultplayer": "igrok_po_umolchaniyu",
            "defaultentity": "suschnost_po_umolchaniyu",
        }
        leaf_mapped = leaf_sh.get(leaf_key, leaf_key)

        def _has_hint(parts_list: list[str], needles: tuple[str, ...]) -> bool:
            for p in parts_list:
                np = norm_ident(p)
                for n in needles:
                    if n in np:
                        return True
            return False

        want_player = _has_hint(parts[:-1], ("player", "игрок", "ifplayer", "if_player"))
        want_mob = _has_hint(parts[:-1], ("mob", "моб", "ifmob", "if_mob"))
        want_entity = _has_hint(parts[:-1], ("entity", "существо", "сущность", "ifentity", "if_entity"))

        domain_sign2 = ""
        if want_player:
            domain_sign2 = "игрокпоусловию"
        elif want_mob:
            domain_sign2 = "мобпоусловию"
        elif want_entity:
            domain_sign2 = "сущностьпоусловию"

        select_cands: list[tuple[str, dict]] = []
        for canon, spec in mod.items():
            if not isinstance(spec, dict):
                continue
            s1 = strip_colors(spec.get("sign1", "")).strip()
            s1n = norm_key(s1)
            if s1n in sign1_aliases:
                s1n = norm_key(sign1_aliases[s1n])
            if s1n != norm_key("Выбрать объект"):
                continue
            if domain_sign2:
                s2n = norm_ident(spec.get("sign2", ""))
                if s2n != domain_sign2:
                    continue
            select_cands.append((canon, spec))

        target = norm_ident(leaf_mapped)
        hits: list[tuple[str, dict]] = []
        for canon, spec in select_cands:
            keys = []
            keys.append(canon)
            keys.extend(spec.get("aliases") or [])
            keys.extend([spec.get("menu", ""), spec.get("gui", ""), spec.get("sign2", "")])
            if any(norm_ident(str(k)) == target for k in keys if k):
                hits.append((canon, spec))

        if not hits:
            # Sugar bridge:
            # select.ifplayer.<leaf> / select.ifmob.<leaf> / select.ifentity.<leaf>
            # should accept if_player condition names and map them to
            # corresponding "Выбрать объект -> * по условию" selector entries.
            if_player_mod = api.get("if_player") or {}
            if_target_menu = ""
            for canon, spec in if_player_mod.items():
                if not isinstance(spec, dict):
                    continue
                keys = [canon]
                keys.extend(spec.get("aliases") or [])
                keys.extend([spec.get("menu", ""), spec.get("gui", ""), spec.get("sign2", "")])
                if any(norm_ident(str(k)) == target for k in keys if k):
                    if_target_menu = norm_ident(
                        strip_colors(spec.get("menu", "")).strip()
                        or strip_colors(spec.get("sign2", "")).strip()
                        or strip_colors(spec.get("gui", "")).strip()
                    )
                    break
            if if_target_menu:
                for canon, spec in select_cands:
                    keys = [canon]
                    keys.extend(spec.get("aliases") or [])
                    keys.extend([spec.get("menu", ""), spec.get("gui", ""), spec.get("sign2", "")])
                    if any(norm_ident(str(k)) == if_target_menu for k in keys if k):
                        hits.append((canon, spec))

        if not hits:
            raise ValueError(f"select: неизвестный селектор `{leaf}` (chain={chain})")

        if len(hits) == 1:
            return hits[0]

        if want_player or want_mob or want_entity:
            filtered = []
            for canon, spec in hits:
                s2 = norm_ident(spec.get("sign2", ""))
                if want_player and s2 == "игрокпоусловию":
                    filtered.append((canon, spec))
                elif want_mob and s2 == "мобпоусловию":
                    filtered.append((canon, spec))
                elif want_entity and s2 == "сущностьпоусловию":
                    filtered.append((canon, spec))
            if len(filtered) == 1:
                return filtered[0]
            if filtered:
                hits = filtered

        opts = ", ".join([f"{c}:{strip_colors(s.get('menu',''))}" for c, s in hits[:8]])
        more = "..." if len(hits) > 8 else ""
        raise ValueError(f"select: неоднозначно `{leaf}`. Варианты: {opts}{more}")

    def resolve_import_path(base: Path, raw: str) -> Path:
        rel = raw.replace("\\", "/")
        if not rel.lower().endswith(".mldsl"):
            rel += ".mldsl"
        return (base.parent / rel).resolve()

    def load_with_imports(entry: Path) -> tuple[list[str], set[str]]:
        """
        Loads file and inlines `import/use/использовать <path>` directives.
        Returns: (lines, namespaces) where namespaces are imported module stems (for optional `ns.` stripping).
        """
        visited: set[Path] = set()
        namespaces: set[str] = set()
        out: list[str] = []

        def rec(p: Path):
            rp = p.resolve()
            if rp in visited:
                return
            visited.add(rp)
            if not rp.exists():
                raise ValueError(f"import: файл не найден: {rp}")
            for raw in rp.read_text(encoding="utf-8-sig").splitlines():
                m = IMPORT_RE.match(raw.strip())
                if m:
                    spec = m.group(1).strip().strip("\"'")
                    namespaces.add(Path(spec).stem)
                    rec(resolve_import_path(rp, spec))
                else:
                    out.append(raw)

        rec(entry)
        return out, namespaces

    def _line_indent(raw: str) -> str:
        i = 0
        while i < len(raw) and raw[i] in (" ", "\t"):
            i += 1
        return raw[:i]

    def _parse_vfunc_params(raw: str, name: str) -> tuple[list[str], dict[str, str]]:
        names: list[str] = []
        defaults: dict[str, str] = {}
        if not (raw or "").strip():
            return names, defaults
        for part in split_args(raw):
            token = (part or "").strip()
            if not token:
                continue
            eq = token.find("=")
            if eq < 0:
                pname = token
                default = None
            else:
                pname = token[:eq].strip()
                default = token[eq + 1 :].strip()
            if not re.match(rf"^{NAME_RE}$", pname):
                raise ValueError(f"vfunc {name}(): недопустимое имя параметра: {pname}")
            if pname in names:
                raise ValueError(f"vfunc {name}(): дублирующийся параметр: {pname}")
            names.append(pname)
            if default is not None:
                defaults[pname] = default
        return names, defaults

    def collect_vfunc_defs(src_lines: list[str]) -> tuple[list[str], dict[str, dict]]:
        vfuncs: dict[str, dict] = {}
        out: list[str] = []
        i = 0
        n = len(src_lines)
        while i < n:
            raw = src_lines[i]
            stripped = (raw or "").strip()
            m = VFUNC_RE.match(stripped)
            if not m:
                out.append(raw)
                i += 1
                continue

            if _line_indent(raw):
                raise ValueError("vfunc: definition must be top-level (no leading indentation)")

            name = (m.group(1) or "").strip()
            if name in vfuncs:
                raise ValueError(f"vfunc {name}(): duplicate definition")
            params_raw = (m.group(2) or "").strip()
            params, defaults = _parse_vfunc_params(params_raw, name)

            i += 1
            body_raw: list[str] = []
            while i < n:
                cur = src_lines[i]
                cur_s = (cur or "").strip()
                if not cur_s:
                    body_raw.append("")
                    i += 1
                    continue
                if _line_indent(cur):
                    body_raw.append(cur)
                    i += 1
                    continue
                break

            if not any((ln or "").strip() for ln in body_raw):
                raise ValueError(f"vfunc {name}(): body is empty")

            nonempty = [ln for ln in body_raw if (ln or "").strip()]
            min_indent = min(len(_line_indent(ln)) for ln in nonempty) if nonempty else 0
            body = [ln[min_indent:] if (ln or "").strip() else "" for ln in body_raw]
            vfuncs[name] = {
                "params": params,
                "defaults": defaults,
                "body": body,
            }
        return out, vfuncs

    def _substitute_params_outside_strings(template: str, mapping: dict[str, str]) -> str:
        s = template or ""
        out: list[str] = []
        i = 0
        in_str = False
        str_ch = ""
        esc = False
        while i < len(s):
            ch = s[i]
            if esc:
                out.append(ch)
                esc = False
                i += 1
                continue
            if ch == "\\":
                out.append(ch)
                esc = True
                i += 1
                continue
            if ch in ('"', "'"):
                if in_str and ch == str_ch:
                    in_str = False
                    str_ch = ""
                elif not in_str:
                    in_str = True
                    str_ch = ch
                out.append(ch)
                i += 1
                continue
            if not in_str:
                m = re.match(rf"{NAME_RE}", s[i:])
                if m:
                    tok = m.group(0)
                    out.append(mapping.get(tok, tok))
                    i += len(tok)
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    def expand_vfunc_calls(src_lines: list[str], vfuncs: dict[str, dict], max_depth: int = 32) -> list[str]:
        if not vfuncs:
            return src_lines

        def expand_list(lines_in: list[str], stack: list[str], depth: int) -> list[str]:
            if depth > max_depth:
                chain = " -> ".join(stack) if stack else "<root>"
                raise ValueError(f"vfunc expansion depth exceeded (>{max_depth}): {chain}")
            out_lines: list[str] = []
            for raw in lines_in:
                stripped = (raw or "").strip()
                if not stripped or stripped.startswith("#"):
                    out_lines.append(raw)
                    continue
                m = BARE_CALL_RE.match(stripped)
                if not m:
                    out_lines.append(raw)
                    continue
                call_name = (m.group(1) or "").strip()
                if call_name not in vfuncs:
                    out_lines.append(raw)
                    continue

                if call_name in stack:
                    chain = " -> ".join([*stack, call_name])
                    raise ValueError(f"vfunc recursion cycle detected: {chain}")
                spec = vfuncs[call_name]
                kv, pos = parse_call_args(m.group(2) or "")
                params: list[str] = list(spec["params"])
                defaults: dict[str, str] = dict(spec["defaults"])
                resolved: dict[str, str] = {}

                if len(pos) > len(params):
                    raise ValueError(
                        f"vfunc {call_name}(): expected at most {len(params)} positional args, got {len(pos)}"
                    )
                for idx, arg in enumerate(pos):
                    resolved[params[idx]] = arg

                for k, v in kv.items():
                    if k not in params:
                        raise ValueError(f"vfunc {call_name}(): unknown argument `{k}`")
                    if k in resolved:
                        raise ValueError(f"vfunc {call_name}(): duplicate argument `{k}`")
                    resolved[k] = v

                for p in params:
                    if p in resolved:
                        continue
                    if p in defaults:
                        resolved[p] = defaults[p]
                    else:
                        raise ValueError(f"vfunc {call_name}(): missing required argument `{p}`")

                base_indent = _line_indent(raw)
                expanded_chunk = []
                for body_line in spec["body"]:
                    if not (body_line or "").strip():
                        expanded_chunk.append("")
                        continue
                    substituted = _substitute_params_outside_strings(body_line, resolved)
                    expanded_chunk.append(base_indent + substituted)

                out_lines.extend(expand_list(expanded_chunk, [*stack, call_name], depth + 1))
            return out_lines

        return expand_list(src_lines, [], 0)

    lines, imported_namespaces = load_with_imports(path)
    lines, vfunc_defs = collect_vfunc_defs(lines)
    lines = expand_vfunc_calls(lines, vfunc_defs)

    # Collect function signatures (name -> param list) in advance so calls can be validated
    # even if the function is declared later in the file.
    func_sigs: dict[str, list[str]] = {}
    for raw in lines:
        m = FUNC_RE.match((raw or "").strip())
        if not m:
            continue
        fname = (m.group(1) or "").strip()
        if not fname:
            continue
        params_raw = (m.group(2) or "").strip()
        params = []
        if params_raw:
            for part in split_args(params_raw):
                pn = (part or "").strip()
                if not pn:
                    continue
                if not re.match(rf"^{NAME_RE}$", pn):
                    raise ValueError(f"func {fname}(): недопустимое имя параметра: {pn}")
                params.append(pn)
        func_sigs[fname] = params
    for vname in vfunc_defs.keys():
        if vname in func_sigs:
            raise ValueError(f"name conflict: `{vname}` defined as both func and vfunc")
    entries: list[dict] = []

    in_block = False
    current_kind = None  # event|func|loop
    current_name = None
    current_loop_ticks = None
    current_actions: list[tuple[str, str, str]] = []
    block_stack: list[str] = []  # nested blocks inside event/func/loop (e.g. if)
    current_func_params: list[str] = []
    current_func_has_return = False

    def flush_block():
        nonlocal current_kind, current_name, current_loop_ticks, current_actions, current_func_params, current_func_has_return
        if not current_kind:
            return

        if current_kind == "event":
            ev_raw = (current_name or "").strip()
            if not ev_raw:
                # Placeholder from exportcode empty sign blocks.
                entries.append({"block": "diamond_block", "name": "Событие игрока||", "args": "no"})
            else:
                ev_name = event_variant_to_name(ev_raw)
                nk = norm_key(ev_name)
                if known_events and nk in known_events:
                    block, menu_name, expected_sign2 = known_events[nk]
                    entries.append({"block": block, "name": f"{menu_name}||{expected_sign2}", "args": "no"})
                elif known_events:
                    raise ValueError(f"неизвестное событие: {ev_name}")
                else:
                    # Fallback when no catalog is available.
                    entries.append({"block": "diamond_block", "name": ev_name, "args": "no"})
        elif current_kind == "func":
            entries.append({"block": "lapis_block", "name": (current_name or ""), "args": "no"})
        elif current_kind == "loop":
            ticks = int(current_loop_ticks or 5)
            ticks = max(5, ticks)
            entries.append({"block": "emerald_block", "name": (current_name or ""), "args": str(ticks)})
        else:
            raise ValueError(f"Unknown block kind: {current_kind}")

        def to_tuple(res):
            pieces, spec = res
            args_str = ",".join(pieces) if pieces else "no"
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
            string_name = sign2
            if expected_sign2:
                string_name = f"{(menu or sign2)}||{expected_sign2}"
            return (block_tok, string_name, args_str)

        # Function prologue: pop args stack into declared param variables (sync-only protocol).
        if current_kind == "func" and current_func_params:
            insert_at = 0
            for pn in current_func_params:
                res = compile_line(
                    api,
                    f"array.get_array(arr=arr({ARGS_STACK_NAME}), number=num({STACK_TOP_INDEX}), var=var({pn}))",
                )
                if not res:
                    raise ValueError("func args: не найдено действие 'Получить элемент массива'")
                current_actions.insert(insert_at, to_tuple(res))
                insert_at += 1
                res = compile_line(
                    api, f"array.remove_array(arr=arr({ARGS_STACK_NAME}), number=num({STACK_TOP_INDEX}))"
                )
                if not res:
                    raise ValueError("func args: не найдено действие 'Удалить элемент массива'")
                current_actions.insert(insert_at, to_tuple(res))
                insert_at += 1

        # Implicit return to keep return stack consistent.
        if current_kind == "func" and not current_func_has_return:
            res = compile_line(
                api, f"array.vstavit_v_massiv(arr=arr({RET_STACK_NAME}), number=num({STACK_TOP_INDEX}), value=text())"
            )
            if not res:
                raise ValueError("implicit return: не найдено действие 'Вставить в массив'")
            current_actions.append(to_tuple(res))

        for block, name, args in current_actions:
            entries.append({"block": block, "name": name, "args": (args or "no")})

        current_kind = None
        current_name = None
        current_loop_ticks = None
        current_actions = []
        current_func_params = []
        current_func_has_return = False

    def begin_new_row():
        # split rows by inserting a newline marker between blocks
        if entries:
            entries.append({"block": "newline"})

    tmp_counter = 0

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Optional namespace sugar:
        # If user wrote `import test2` and then uses `test2.hello()`, strip `test2.`.
        # Server has no namespaces; this is only readability sugar (collisions are user's responsibility).
        for ns in imported_namespaces:
            if ns:
                line = re.sub(rf"\b{re.escape(ns)}\.", "", line)

        # Close nested blocks first (so } inside event/func doesn't flush the whole outer block).
        if line == "}" and block_stack:
            kind = block_stack.pop()
            if kind == "if":
                # Exit the server-side piston bracket by advancing the code cursor without placing anything.
                # (Using "air" as a pause causes some servers to desync/teleport the player.)
                current_actions.append(("skip", "", "no"))
            elif kind == "select":
                prev = select_stack.pop() if select_stack else None
                restore_default = select_default_stack.pop() if select_default_stack else DEFAULT_SELECT_PLAYER
                current_select = prev
                if prev is not None:
                    current_actions.append(prev)
                else:
                    # Restore to default selection to avoid leaking selection outside the scope.
                    # Heuristic: if the last select was entity-like, restore entity default, else player default.
                    # (If we don't know, prefer player.)
                    current_actions.append(restore_default)
                    current_select = restore_default
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
            current_name = (m_ev.group(1) or m_ev.group(2) or "").strip()
            in_block = True
            continue
        m_fn = FUNC_RE.match(line)
        if m_fn:
            flush_block()
            begin_new_row()
            current_kind = "func"
            current_name = m_fn.group(1)
            params_raw = (m_fn.group(2) or "").strip()
            params = func_sigs.get(current_name or "", [])
            if params_raw and not params:
                # should not happen (we pre-scanned), but keep safe
                params = [p.strip() for p in split_args(params_raw) if p.strip()]
            current_func_params = params
            current_func_has_return = False
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

        # Selection (Выбрать объект) sugar:
        # - select.<alias>(args?)
        # - select.player.ifplayer.<alias>(args?)  (only last segment is matched; earlier segments are hints)
        # - select.<alias> { ... }  (restores previous selection on })
        m_sel = SELECT_RE.match(line)
        if m_sel:
            chain = (m_sel.group(1) or "").strip()
            arg_str = (m_sel.group(2) or "").strip()
            has_block = bool(m_sel.group(3))

            prev_select = current_select
            canon, _spec = find_select_action(chain)
            sel_tuple, sel_spec = compile_action_tuple("misc", canon, arg_str)
            current_actions.append(sel_tuple)
            current_select = sel_tuple

            if has_block:
                block_stack.append("select")
                select_stack.append(prev_select)
                dom = select_domain(sel_spec)
                select_default_stack.append(DEFAULT_SELECT_ENTITY if dom == "entity" else DEFAULT_SELECT_PLAYER)
            continue

        # Special-case: allow simple nested return in message:
        #   player.message(foo("x"))
        # becomes:
        #   __tmpN = foo()
        #   player.message("%var(__tmpN)%")
        m_nested_msg = re.match(r"^\s*player\.message\s*\(\s*([\w\u0400-\u04FF]+)\s*\((.*)\)\s*\)\s*;?\s*$", line, re.I)
        if m_nested_msg:
            fn = (m_nested_msg.group(1) or "").strip()
            inside = (m_nested_msg.group(2) or "").strip()
            tmp_counter += 1
            tmp = f"{TMP_VAR_PREFIX}{tmp_counter}"
            builtins = compile_builtin(api, f"{tmp} = {fn}({inside})", func_sigs=func_sigs)
            if not builtins:
                raise ValueError(f"Не получилось скомпилировать вызов функции {fn}() для вложенного message()")
            for pieces, spec in builtins:
                args_str = ",".join(pieces)
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
            # Now emit the message itself using the computed tmp var.
            res = compile_line(api, f'player.message("%var({tmp})%")')
            if not res:
                raise ValueError("Не найдено действие player.message()")
            pieces, spec = res
            args_str = ",".join(pieces)
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

        m_ret = re.match(r"^\s*return(?:\s*\(\s*(.*?)\s*\)\s*|\s+(.*))\s*$", line, re.I)
        if m_ret:
            if current_kind != "func":
                raise ValueError("return можно использовать только внутри func{}")
            current_func_has_return = True
            expr = (m_ret.group(1) or m_ret.group(2) or "").strip()
            # default: return empty text
            if not expr:
                expr = "text()"
            else:
                # normalize simple literals for return
                if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
                    expr = f"text({expr[1:-1]})"
                elif re.match(r"^-?\d+(?:\.\d+)?$", expr):
                    expr = f"num({expr})"
                elif re.match(rf"^{NAME_RE}$", expr) and not expr.lower().startswith(("text(", "num(", "var(", "arr(", "loc(")):
                    expr = f"var({expr})"
            res = compile_line(
                api,
                f"array.vstavit_v_massiv(arr=arr({RET_STACK_NAME}), number=num({STACK_TOP_INDEX}), value={expr})",
            )
            if not res:
                raise ValueError("return: не найдено действие 'Вставить в массив'")
            pieces, spec = res
            args_str = ",".join(pieces)
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

        builtins = compile_builtin(api, line, func_sigs=func_sigs, debug_stacks=debug_stacks)
        if builtins:
            for pieces, spec in builtins:
                args_str = ",".join(pieces)
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
