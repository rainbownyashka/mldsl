import unittest

from mldsl_exportcode import exportcode_to_mldsl


class ExportcodeContractTests(unittest.TestCase):
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
        self.assertIn("misc.имя_равно(", out)
        self.assertIn("автоподбор действия по сундуку: from=misc.кандидат_низкий", out)
        self.assertIn("-> to=misc.имя_равно", out)


if __name__ == "__main__":
    unittest.main()
