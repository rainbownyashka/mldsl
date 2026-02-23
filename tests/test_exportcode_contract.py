import unittest

from mldsl_exportcode import exportcode_to_mldsl


class ExportcodeContractTests(unittest.TestCase):
    def test_resolver_prefers_exact_sign1_sign2_over_sign1_fallback(self):
        api = {
            "player": {
                "soobschenie": {
                    "aliases": ["сообщение"],
                    "sign1": "Действие игрока",
                    "sign2": "Сообщение",
                    "params": [],
                    "enums": [],
                },
                "imya_ravno": {
                    "aliases": ["имя_равно"],
                    "sign1": "Действие игрока",
                    "sign2": "Имя равно",
                    "params": [],
                    "enums": [],
                },
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "Сообщение", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 0, "id": "minecraft:book", "displayName": "Любой"}],
                        },
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("player.сообщение()", out)
        self.assertNotIn("player.имя_равно(", out)

    def test_air_placeholder_block_is_not_emitted_as_action(self):
        api = {
            "if_player": {
                "soobschenie_ravno": {
                    "aliases": ["сообщение_равно"],
                    "sign1": "Если игрок",
                    "sign2": "Сообщение равно",
                    "params": [],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Событие чата", "", ""]},
                        {"block": "minecraft:planks", "pos": {"x": 8, "y": 1, "z": 0}, "sign": ["Если игрок", "Сообщение равно", "", ""]},
                        # AIR with copied sign text from runtime is a technical marker and must be ignored.
                        {"block": "minecraft:air", "pos": {"x": 6, "y": 1, "z": 0}, "sign": ["Если игрок", "Сообщение равно", "", ""]},
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("if_player.сообщение_равно()", out)
        self.assertEqual(out.count("if_player.сообщение_равно()"), 1)

    def test_world_event_gold_block_is_event_not_row(self):
        api = {}
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {
                            "block": "minecraft:gold_block",
                            "pos": {"x": 10, "y": 1, "z": 0},
                            "sign": ["Событие мира", "Запуск мира", "", ""],
                        },
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "", "", ""],
                        },
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn('event("Запуск мира") {', out)
        self.assertNotIn('row("Запуск мира") {', out)

    def test_empty_sign_becomes_noaction(self):
        api = {}
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "", "", ""]},
                        {"block": "minecraft:cobblestone", "pos": {"x": 8, "y": 1, "z": 0}, "sign": ["Действие игрока", "", "", ""]},
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("event(", out)
        self.assertIn("player.noaction()", out)

    def test_fully_empty_sign_has_explicit_empty_sign_warning(self):
        api = {}
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {"block": "minecraft:cobblestone", "pos": {"x": 8, "y": 1, "z": 0}, "sign": ["", "", "", ""]},
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("пустая табличка: sign1/sign2/gui/menu пустые после нормализации", out)
        self.assertIn("# UNKNOWN:", out)

    def test_side_piston_west_open_east_close(self):
        api = {
            "player": {
                "soobschenie": {
                    "aliases": ["сообщение"],
                    "sign1": "Действие игрока",
                    "sign2": "Сообщение",
                    "params": [],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {"block": "minecraft:planks", "pos": {"x": 8, "y": 1, "z": 0}, "sign": ["Если игрок", "", "", ""]},
                        {"block": "minecraft:piston", "pos": {"x": 7, "y": 1, "z": 0}, "facing": "west"},
                        {"block": "minecraft:cobblestone", "pos": {"x": 6, "y": 1, "z": 0}, "sign": ["Действие игрока", "Сообщение", "", ""]},
                        {"block": "minecraft:piston", "pos": {"x": 5, "y": 1, "z": 0}, "facing": "east"},
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("{", out)
        self.assertIn("}", out)
        self.assertIn("player.сообщение()", out)

    def test_chest_autopick_warn_reports_alias_transition(self):
        api = {
            "misc": {
                "candidate_low": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Игрок по условию",
                    "aliases": ["кандидат_низкий"],
                    "params": [],
                    "enums": [{"name": "tip", "slot": 0, "options": {"Неподходящее": "WRONG"}}],
                },
                "imya_ravno": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Игрок по условию",
                    "aliases": ["имя_равно"],
                    "params": [],
                    "enums": [{"name": "tip", "slot": 0, "options": {"Имя равно": "NAME_EQUALS"}}],
                },
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:planks",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Выбрать обьект", "Игрок по условию", "", ""],
                            "hasChest": True,
                            "chestItems": [
                                {
                                    "slot": 0,
                                    "id": "minecraft:book",
                                    "isEnum": True,
                                    "enumOptions": ["Имя равно", "Неподходящее"],
                                    "enumSelectedIndex": 0,
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("select.ifplayer.имя_равно(", out)
        self.assertIn("автоподбор действия по сундуку: from=misc.кандидат_низкий", out)
        self.assertIn("-> to=misc.имя_равно", out)

    def test_select_condition_scope_for_mob_and_entity(self):
        api = {
            "misc": {
                "mob_name_eq": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Моб по условию",
                    "aliases": ["имя_равно"],
                    "menu": "Имя равно",
                    "params": [{"name": "text", "slot": 0, "mode": "TEXT"}],
                    "enums": [],
                },
                "entity_name_eq": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Сущность по условию",
                    "aliases": ["имя_равно"],
                    "menu": "Имя равно",
                    "params": [{"name": "text", "slot": 0, "mode": "TEXT"}],
                    "enums": [],
                },
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:planks",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Выбрать обьект", "Моб по условию", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 0, "id": "minecraft:book", "displayName": "Z"}],
                        },
                        {
                            "block": "minecraft:planks",
                            "pos": {"x": 6, "y": 1, "z": 0},
                            "sign": ["Выбрать обьект", "Сущность по условию", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 0, "id": "minecraft:book", "displayName": "E"}],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn('select.ifmob.имя_равно(text="Z")', out)
        self.assertIn('select.ifentity.имя_равно(text="E")', out)

    def test_select_translation_avoids_generic_deystviya_alias(self):
        api = {
            "select": {
                "unnamed_6": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Все сущности",
                    "menu": "Выбрать всех сущностей",
                    "aliases": ["deystviya", "unnamed_6", "vse_suschnosti", "все_сущности", "действия"],
                    "params": [],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {"block": "minecraft:purpur_block", "pos": {"x": 8, "y": 1, "z": 0}, "sign": ["Выбрать обьект", "Все сущности", "", ""], "hasChest": False},
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("select.все_сущности()", out)
        self.assertNotIn("select.действия()", out)
        self.assertNotIn("select.deystviya()", out)

    def test_select_ifentity_avoids_category_aliases(self):
        api = {
            "select": {
                "ifentity_znachenie_ravno": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Сущность по условию",
                    "aliases": [
                        "ifentity_znachenie_ravno",
                        "peremennaya",
                        "suschnost_po_usloviyu",
                        "znachenie_ravno",
                        "значение_равно",
                        "переменная",
                        "сущность_по_условию",
                    ],
                    "params": [{"name": "num", "slot": 0, "mode": "NUMBER"}],
                    "enums": [{"name": "tip_proverki", "slot": 13, "options": {"> (Больше)": "Больше"}}],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:planks",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Выбрать обьект", "Сущность по условию", "", ""],
                            "hasChest": True,
                            "chestItems": [
                                {"slot": 0, "id": "minecraft:apple", "displayName": "5"},
                                {"slot": 13, "id": "minecraft:anvil", "displayName": "> (Больше)"},
                            ],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("select.ifentity.значение_равно(", out)
        self.assertNotIn("select.ifentity.переменная(", out)
        self.assertNotIn("select.ifentity.сущность_по_условию(", out)

    def test_select_module_actions_are_scoped_by_condition_domain(self):
        api = {
            "select": {
                "ifentity_sravnit_chisla_oblegchennaya_versiya": {
                    "sign1": "Выбрать обьект",
                    "sign2": "Сущность по условию",
                    "aliases": ["сравнить_число_облегчённо", "сущность_по_условию"],
                    "params": [
                        {"name": "num", "slot": 0, "mode": "NUMBER"},
                        {"name": "num2", "slot": 1, "mode": "NUMBER"},
                    ],
                    "enums": [{"name": "tip_proverki", "slot": 13, "options": {"> (Больше)": "Больше"}}],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:planks",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Выбрать обьект", "Сущность по условию", "", ""],
                            "hasChest": True,
                            "chestItems": [
                                {"slot": 0, "id": "minecraft:apple", "displayName": "5"},
                                {"slot": 1, "id": "minecraft:apple", "displayName": "4"},
                                {"slot": 13, "id": "minecraft:anvil", "displayName": "> (Больше)"},
                            ],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("select.ifentity.сравнить_число_облегчённо(", out)

    def test_text_mode_keeps_variable_value_not_stringified(self):
        api = {
            "player": {
                "set_text": {
                    "sign1": "Действие игрока",
                    "sign2": "Тест текст",
                    "aliases": ["set_text"],
                    "params": [{"name": "text", "slot": 9, "mode": "TEXT"}],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "Тест текст", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 9, "id": "minecraft:magma_cream", "displayName": "myVar"}],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("player.set_text(text=myVar)", out)
        self.assertNotIn('text="myVar"', out)

    def test_apple_mode_keeps_variable_value_not_stringified(self):
        api = {
            "player": {
                "set_apple": {
                    "sign1": "Действие игрока",
                    "sign2": "Тест яблоко",
                    "aliases": ["set_apple"],
                    "params": [{"name": "value", "slot": 9, "mode": "APPLE"}],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "Тест яблоко", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 9, "id": "minecraft:magma_cream", "displayName": "var_save(savedName)", "lore": ["Сохраненная"]}],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("player.set_apple(value=var_save(savedName))", out)
        self.assertNotIn('value="var_save(savedName)"', out)

    def test_apple_mode_keeps_loc_name_raw(self):
        api = {
            "player": {
                "set_apple": {
                    "sign1": "Действие игрока",
                    "sign2": "Тест яблоко",
                    "aliases": ["set_apple"],
                    "params": [{"name": "value", "slot": 9, "mode": "APPLE"}],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "Тест яблоко", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 9, "id": "minecraft:apple", "displayName": "LOC_NAME"}],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("player.set_apple(value=apple.LOC_NAME)", out)
        self.assertNotIn('value="apple.LOC_NAME"', out)

    def test_apple_mode_keeps_prefixed_constant_as_is(self):
        api = {
            "player": {
                "set_apple": {
                    "sign1": "Действие игрока",
                    "sign2": "Тест яблоко",
                    "aliases": ["set_apple"],
                    "params": [{"name": "value", "slot": 9, "mode": "APPLE"}],
                    "enums": [],
                }
            }
        }
        export_obj = {
            "version": 2,
            "rows": [
                {
                    "row": 0,
                    "glass": {"x": 10, "y": 0, "z": 0},
                    "blocks": [
                        {"block": "minecraft:diamond_block", "pos": {"x": 10, "y": 1, "z": 0}, "sign": ["Событие игрока", "Вход", "", ""]},
                        {
                            "block": "minecraft:cobblestone",
                            "pos": {"x": 8, "y": 1, "z": 0},
                            "sign": ["Действие игрока", "Тест яблоко", "", ""],
                            "hasChest": True,
                            "chestItems": [{"slot": 9, "id": "minecraft:apple", "displayName": "apple.POSCHETOTAM"}],
                        },
                    ],
                }
            ],
        }
        out = exportcode_to_mldsl(export_obj, api)
        self.assertIn("player.set_apple(value=apple.POSCHETOTAM)", out)


if __name__ == "__main__":
    unittest.main()
