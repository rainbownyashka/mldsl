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


if __name__ == "__main__":
    unittest.main()
