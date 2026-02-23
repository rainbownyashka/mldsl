import pytest

import mldsl_compile


def _api_base():
    return {
        "misc": {
            "vybrat_igroka_po_umolchaniyu": {
                "aliases": ["выбрать_игрока_по_умолчанию"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по умолчанию",
                "menu": "Игрок по умолчанию",
                "params": [],
                "enums": [],
            },
            "vybrat_suschnost_po_umolchaniyu": {
                "aliases": ["выбрать_сущность_по_умолчанию"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по умолчанию",
                "menu": "Сущность по умолчанию",
                "params": [],
                "enums": [],
            },
            "ifplayer_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifmob_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Моб по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifentity_peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Выбрать обьект",
                "sign2": "Сущность по условию",
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "ifplayer_derzhit_predmet": {
                "aliases": ["держит_предмет"],
                "sign1": "Выбрать обьект",
                "sign2": "Игрок по условию",
                "menu": "Держит предмет",
                "params": [{"name": "item", "slot": 9, "mode": "ITEM"}],
                "enums": [],
            },
        },
        "if_player": {
            "peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "menu": "Переменная существует",
                "params": [{"name": "var", "slot": 13, "mode": "VARIABLE"}],
                "enums": [],
            },
            "derzhit_predmet": {
                "aliases": ["держит_предмет", "держит"],
                "menu": "Держит предмет",
                "params": [{"name": "item", "slot": 9, "mode": "ITEM"}],
                "enums": [],
            },
        },
        "if_value": {
            "peremennaya_suschestvuet": {
                "aliases": ["переменная_существует"],
                "sign1": "Если переменная",
                "sign2": "Переменная существует",
                "params": [
                    {"name": "var", "slot": 13, "mode": "VARIABLE"},
                    {"name": "var2", "slot": 31, "mode": "VARIABLE"},
                ],
                "enums": [],
            },
            "number": {
                "aliases": ["сравнить_число_легко"],
                "sign1": "Если переменная",
                "sign2": "Сравнить число (Легко)",
                "params": [
                    {"name": "num", "slot": 10, "mode": "NUMBER"},
                    {"name": "num2", "slot": 16, "mode": "NUMBER"},
                ],
                "enums": [],
            },
        },
        "var": {
            "set_value": {
                "aliases": ["set_value"],
                "sign1": "Присв. переменную",
                "sign2": "=",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value", "slot": 10, "mode": "ANY"},
                ],
                "enums": [],
            },
            "set_sum": {
                "aliases": ["set_sum"],
                "sign1": "Присв. переменную",
                "sign2": "+",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "values", "slot": 10, "mode": "ANY_ARRAY"},
                ],
                "enums": [],
            },
            "set_difference": {
                "aliases": ["set_difference"],
                "sign1": "Присв. переменную",
                "sign2": "-",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value1", "slot": 10, "mode": "ANY"},
                    {"name": "value2", "slot": 11, "mode": "ANY"},
                ],
                "enums": [],
            },
            "set_product": {
                "aliases": ["set_product"],
                "sign1": "Присв. переменную",
                "sign2": "*",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "values", "slot": 10, "mode": "ANY_ARRAY"},
                ],
                "enums": [],
            },
            "set_quotient": {
                "aliases": ["set_quotient"],
                "sign1": "Присв. переменную",
                "sign2": "/",
                "params": [
                    {"name": "var", "slot": 9, "mode": "VARIABLE"},
                    {"name": "value1", "slot": 10, "mode": "ANY"},
                    {"name": "value2", "slot": 11, "mode": "ANY"},
                ],
                "enums": [],
            },
        },
        "player": {
            "msg": {
                "aliases": ["msg"],
                "sign1": "Действие игрока",
                "sign2": "Сообщение",
                "params": [{"name": "text", "slot": 9, "mode": "TEXT"}],
                "enums": [],
            }
        },
        "game": {
            "call_function": {
                "aliases": ["call_function", "вызвать_функцию"],
                "sign1": "Действие игрока",
                "sign2": "Вызвать функцию",
                "params": [{"name": "text", "slot": 13, "mode": "TEXT"}],
                "enums": [],
            },
        },
        "array": {
            "vstavit_v_massiv": {
                "aliases": ["vstavit_v_massiv"],
                "sign1": "Действие игрока",
                "sign2": "Вставить в массив",
                "params": [
                    {"name": "arr", "slot": 10, "mode": "ARRAY"},
                    {"name": "num", "slot": 13, "mode": "NUMBER"},
                    {"name": "value", "slot": 16, "mode": "ANY"},
                ],
                "enums": [],
            },
        },
        "if_game": {},
        "select": {},
    }


def _compile(tmp_path, monkeypatch, lines, api=None):
    path = tmp_path / "case.mldsl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: (api or _api_base()))
    return mldsl_compile.compile_entries(path)


def test_select_if_player_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_player.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Игрок по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_if_mob_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_mob.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Моб по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_if_entity_var_exists_success(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_entity.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["name"] == "Переменная существует||Сущность по условию"
    assert entries[1]["args"] == "slot(13)=var(x)"


def test_select_bridge_leaf_map_derzhit(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'select.if_player.держит(item=item("minecraft:stick"))', "}"],
    )
    assert entries[1]["name"] == "Держит предмет||Игрок по условию"


def test_select_unknown_leaf_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="select: неизвестный селектор"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', "select.if_player.unknown_leaf(var=x)", "}"],
        )


def test_select_ambiguous_without_domain_hint_fail_fast(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="select: неоднозначно"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', "select.переменная_существует(var=x)", "}"],
        )


def test_assignment_sugars_compile(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "a += 1", "a -= 1", "a *= 2", "a /= 2", "}"],
    )
    names = [e["name"] for e in entries[1:]]
    assert "+||+" in names
    assert "-||-" in names
    assert "*||*" in names
    assert "/||/" in names


def test_call_with_equals_inside_text_not_parsed_as_assignment(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'player.msg("[mnist] sum=%var(a)% pred=%var(b)%")', "}"],
    )
    assert entries[1]["name"] == "Сообщение||Сообщение"
    assert "slot(9)=text([mnist] sum=%var(a)% pred=%var(b)%)" == entries[1]["args"]


def test_assignment_loc_normalized_to_paper_item(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'base = loc("180.30 4.00 181.30 -36.15 -7.20")', "}"],
    )
    assert entries[1]["name"] == "=||="
    assert (
        'slot(9)=var(base),slot(10)=item(minecraft:paper, name="180.30 4.00 181.30 -36.15 -7.20")'
        == entries[1]["args"]
    )


def test_variable_param_allows_item_with_warn(tmp_path, monkeypatch, capsys):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'var.set_value(var=item("minecraft:magma_cream", name="&atest&btest"), value=1)', "}"],
    )
    err = capsys.readouterr().err
    assert "VARIABLE-аргумент" in err
    assert "item(...)" in err
    assert entries[1]["name"] == "=||="
    assert 'slot(9)=item("minecraft:magma_cream", name="§atest§btest"),slot(10)=1' == entries[1]["args"]


def test_unknown_named_enum_fails_fast(tmp_path, monkeypatch):
    api = _api_base()
    api["if_value"]["number"]["enums"] = [{"name": "tip_proverki", "slot": 13, "options": {"==": 0, ">": 1}}]
    with pytest.raises(ValueError, match="неизвестные именованные аргументы/enum"):
        _compile(
            tmp_path,
            monkeypatch,
            [
                'event("Вход") {',
                'if_value.сравнить_число_легко(num=1, num2=2, tip_proverki2="==")',
                "}",
            ],
            api=api,
        )


def test_amp_replaced_with_section_unescaped_only(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', r'player.msg("&aok \&bkeep_amp")', "}"],
    )
    assert entries[1]["name"] == "Сообщение||Сообщение"
    assert entries[1]["args"] == "slot(9)=text(§aok &bkeep_amp)"


def test_assignment_dynamic_placeholder_lhs_compiles(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "__mn_row_%var(__mn_z)% += __mn_pix", "}"],
    )
    args_all = "\n".join(str(e.get("args") or "") for e in entries)
    assert "__mn_row_%var(__mn_z)%" in args_all


def test_assignment_non_numeric_rhs_raises(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="supports numeric expressions only"):
        _compile(
            tmp_path,
            monkeypatch,
            ['event("Вход") {', 'a += "txt"', "}"],
        )


def test_assignment_negative_literal_does_not_compile_as_product(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "a = -1.483046211", "}"],
    )
    names = [e["name"] for e in entries[1:]]
    assert "*||*" not in names
    assert "=||=" in names
    assert any("slot(10)=num(-1.483046211)" in (e.get("args") or "") for e in entries)


def test_assignment_constant_unary_minus_expressions_fold_to_single_set_value(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "a = -(1 + 2)", "b = -(-3.5)", "}"],
    )
    names = [e["name"] for e in entries[1:]]
    assert names.count("=||=") == 2
    assert "+||+" not in names
    assert "-||-" not in names
    assert "*||*" not in names
    assert "/||/" not in names
    args = [e.get("args") or "" for e in entries]
    assert any("slot(10)=num(-3)" in a for a in args)
    assert any("slot(10)=num(3.5)" in a for a in args)


def test_inline_if_blocks_match_multiline_semantics(tmp_path, monkeypatch):
    inline_entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            'if_value.сравнить_число_легко(__mn_x, 28, tip_proverki="≥ (Больше или равно)") { __mn_x = 0 __mn_z += 1 }',
            'if_value.сравнить_число_легко(__mn_z, 28, tip_proverki="≥ (Больше или равно)") { __mn_done = 1 }',
            "}",
        ],
    )

    multiline_entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            'if_value.сравнить_число_легко(__mn_x, 28, tip_proverki="≥ (Больше или равно)") {',
            "    __mn_x = 0",
            "    __mn_z += 1",
            "}",
            'if_value.сравнить_число_легко(__mn_z, 28, tip_proverki="≥ (Больше или равно)") {',
            "    __mn_done = 1",
            "}",
            "}",
        ],
    )

    assert inline_entries == multiline_entries


def test_text_param_bare_identifier_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "player.msg(text=myVar)", "}"],
    )
    assert entries[1]["args"] == "slot(9)=var(myVar)"


def test_text_param_quoted_literal_normalizes_without_quotes(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'player.msg(text="abc")', "}"],
    )
    assert entries[1]["args"] == "slot(9)=text(abc)"


def test_if_value_var_exists_single_var_is_mirrored_to_var2(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "if_value.переменная_существует(var=x)", "}"],
    )
    assert entries[1]["args"] == "slot(13)=var(x),slot(31)=var(x)"


def test_if_value_block_form_compiles_as_condition_scope(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        [
            'event("Вход") {',
            "    if_value.переменная_существует(var=x) {",
            '        player.msg(text="ok")',
            "    }",
            "}",
        ],
    )
    assert entries[1]["name"] == "Переменная существует||Переменная существует"
    assert entries[2]["name"] == "Сообщение||Сообщение"
    assert any(e.get("block") == "skip" for e in entries)


def test_number_param_bare_identifier_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "if_value.сравнить_число_легко(a, b)", "}"],
    )
    assert entries[1]["args"] == "slot(10)=var(a),slot(16)=var(b)"


def test_number_param_selected_placeholder_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', 'if_value.сравнить_число_легко("%selected%idx", 1)', "}"],
    )
    assert entries[1]["args"] == "slot(10)=var(%selected%idx),slot(16)=num(1)"


def test_number_param_selected_placeholder_expression_compiles_to_temp_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "if_value.сравнить_число_легко(%selected%idx+1, 1)", "}"],
    )
    assert any("__mldsl_tmpargf" in (e.get("args") or "") for e in entries[:-1])
    assert "slot(10)=var(__mldsl_tmpargf" in (entries[-1].get("args") or "")


def test_any_param_selected_placeholder_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "var.set_value(var=a, value=%selected%vartest)", "}"],
    )
    assert entries[1]["args"] == "slot(9)=var(a),slot(10)=var(%selected%vartest)"


def test_text_param_formula_is_compiled_into_actions_with_temp_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "player.msg(text=%player%money + 5)", "}"],
    )
    assert len(entries) >= 3
    assert any(isinstance(e.get("args"), str) and "__mldsl_tmpargf" in e.get("args", "") for e in entries[:-1])
    assert "slot(9)=var(__mldsl_tmpargf" in (entries[-1].get("args") or "")


def test_text_param_formula_without_spaces_is_compiled_too(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "player.msg(text=%player%money+5)", "}"],
    )
    assert len(entries) >= 3
    assert "slot(9)=var(__mldsl_tmpargf" in (entries[-1].get("args") or "")


def test_item_param_placeholder_variable_wraps_to_var(tmp_path, monkeypatch):
    entries = _compile(
        tmp_path,
        monkeypatch,
        ['event("Вход") {', "select.if_player.держит(item=%selected%tool)", "}"],
    )
    assert entries[1]["args"] == "slot(9)=var(%selected%tool)"


def test_multiline_call_limit_reserves_closing_brace(tmp_path, monkeypatch):
    path = tmp_path / "case_limit.mldsl"
    path.write_text(
        "\n".join(
            [
                'event("Вход") {',
                "    player.msg(",
                '        text="very_very_very_very_long_text_value"',
                "    )",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mldsl_compile, "load_api", lambda: _api_base())
    monkeypatch.setenv("MLDSL_NORMALIZED_CALL_LIMIT", "40")
    with pytest.raises(ValueError, match="reserved for closing '}'"):
        mldsl_compile.compile_entries(path)


def test_row_limit_43_uses_call_and_helper_func(tmp_path, monkeypatch):
    lines = ['event("Вход") {']
    for i in range(44):
        lines.append(f'    player.msg(text="m{i}")')
    lines.append("}")

    entries = _compile(tmp_path, monkeypatch, lines)
    blocks = [e.get("block") for e in entries]
    args = [e.get("args") for e in entries]
    names = [e.get("name") for e in entries]

    assert "lapis_block" in blocks
    assert any(isinstance(a, str) and "slot(13)=text(__autosplit_row_" in a for a in args)
    assert any(isinstance(n, str) and n.startswith("__autosplit_row_") for n in names)


def test_row_limit_autosplit_prints_warning_to_stderr(tmp_path, monkeypatch, capsys):
    lines = ['event("Вход") {']
    for i in range(44):
        lines.append(f'    player.msg(text="m{i}")')
    lines.append("}")

    _compile(tmp_path, monkeypatch, lines)
    err = capsys.readouterr().err
    assert "[warn] row auto-split:" in err
    assert "part#1 -> call(__autosplit_row_" in err


def test_row_limit_nested_single_if_fallback_to_newline_split(tmp_path, monkeypatch):
    lines = ['event("Вход") {', "    if_value.переменная_существует(var=x) {"]
    for i in range(60):
        lines.append(f'        player.msg(text="m{i}")')
    lines.extend(["    }", "}"])
    entries = _compile(tmp_path, monkeypatch, lines)
    assert any(e.get("block") == "newline" for e in entries)


def test_row_limit_mixed_split_keeps_autofunc_targets_resolved(tmp_path, monkeypatch):
    lines = ['event("Вход") {']
    for i in range(42):
        lines.append(f'    player.msg(text="a{i}")')
    lines.append("    if_value.переменная_существует(var=x) {")
    for i in range(60):
        lines.append(f'        player.msg(text="b{i}")')
    lines.extend(["    }", "}"])

    entries = _compile(tmp_path, monkeypatch, lines)
    call_targets = set()
    for e in entries:
        args = e.get("args") or ""
        if "slot(13)=text(__autosplit_row_" in args:
            target = args.split("slot(13)=text(", 1)[1].split(")", 1)[0]
            call_targets.add(target)
    func_names = {e.get("name") for e in entries if e.get("block") == "lapis_block"}
    assert call_targets
    assert call_targets.issubset(func_names)


def test_row_wrap_continuation_rows_keep_leading_header(tmp_path, monkeypatch):
    lines = ['event("Вход") {', "    if_value.переменная_существует(var=x) {"]
    for i in range(70):
        lines.append(f'        player.msg(text="m{i}")')
    lines.extend(["    }", "}"])

    entries = _compile(tmp_path, monkeypatch, lines)
    prev_newline = True
    header_blocks = {"diamond_block", "lapis_block", "emerald_block"}
    for e in entries:
        if e.get("block") == "newline":
            prev_newline = True
            continue
        if prev_newline:
            assert e.get("block") in header_blocks
        prev_newline = False


def test_autosplit_postpass_collapses_single_call_trampoline():
    entries = [
        {"block": "diamond_block", "name": "Событие игрока||", "args": "no"},
        {"block": "nether_brick", "name": "Вызвать функцию||Вызвать функцию", "args": "slot(13)=text(__autosplit_row_1)"},
        {"block": "newline"},
        {"block": "lapis_block", "name": "__autosplit_row_1", "args": "no"},
        {"block": "nether_brick", "name": "Вызвать функцию||Вызвать функцию", "args": "slot(13)=text(__autosplit_row_2)"},
        {"block": "newline"},
        {"block": "lapis_block", "name": "__autosplit_row_2", "args": "no"},
        {"block": "iron_block", "name": "Установить (=)||=", "args": "slot(13)=var(x),slot(27)=num(1)"},
    ]
    compact, collapsed = mldsl_compile._collapse_autosplit_trampoline_funcs(entries)
    assert collapsed == 1
    assert any(e.get("block") == "lapis_block" and e.get("name") == "__autosplit_row_2" for e in compact)
    assert not any(e.get("block") == "lapis_block" and e.get("name") == "__autosplit_row_1" for e in compact)
    assert any(
        e.get("name") == "Вызвать функцию||Вызвать функцию"
        and e.get("args") == "slot(13)=text(__autosplit_row_2)"
        for e in compact
    )


def test_autosplit_postpass_promotes_named_wrapper_to_target():
    entries = [
        {"block": "diamond_block", "name": "Событие игрока||", "args": "no"},
        {"block": "nether_brick", "name": "Вызвать функцию||Вызвать функцию", "args": "slot(13)=text(foo)"},
        {"block": "newline"},
        {"block": "lapis_block", "name": "foo", "args": "no"},
        {"block": "nether_brick", "name": "Вызвать функцию||Вызвать функцию", "args": "slot(13)=text(__autosplit_row_1)"},
        {"block": "newline"},
        {"block": "lapis_block", "name": "__autosplit_row_1", "args": "no"},
        {"block": "iron_block", "name": "Установить (=)||=", "args": "slot(13)=var(x),slot(27)=num(1)"},
    ]
    compact, promoted = mldsl_compile._promote_autosplit_targets_into_named_wrappers(entries)
    assert promoted == 1
    assert not any(e.get("block") == "lapis_block" and e.get("name") == "__autosplit_row_1" for e in compact)
    assert any(e.get("block") == "lapis_block" and e.get("name") == "foo" for e in compact)
    assert any(
        e.get("name") == "Вызвать функцию||Вызвать функцию"
        and e.get("args") == "slot(13)=text(foo)"
        for e in compact
    )


def test_func_autosplit_does_not_emit_extra_named_continuation_header(tmp_path, monkeypatch):
    lines = ["func heavy {"]
    for i in range(43):
        lines.append(f'    player.msg(text="m{i}")')
    lines.extend(["}", 'event("Вход") {', "    call(heavy)", "}"])

    entries = _compile(tmp_path, monkeypatch, lines)
    heavy_headers = [e for e in entries if e.get("block") == "lapis_block" and e.get("name") == "heavy"]
    assert len(heavy_headers) == 1
    assert any(
        e.get("name") == "Вызвать функцию||Вызвать функцию"
        and "__autosplit_row_" in (e.get("args") or "")
        for e in entries
    )
