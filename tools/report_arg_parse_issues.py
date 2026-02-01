import json
import importlib.util
from pathlib import Path


from mldsl_paths import arg_parse_issues_path, default_minecraft_export_path, ensure_dirs

EXPORT_PATH = default_minecraft_export_path()
TOOLS_PATH = Path(__file__).resolve().parent / "extract_regallactions_args.py"
OUT_PATH = arg_parse_issues_path()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("extract_regallactions_args", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_export_lines(path: Path) -> list[str]:
    data = path.read_bytes().replace(b"\x00", b"")
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()


def main():
    ensure_dirs()
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(
            "Не найден `regallactions_export.txt`.\n"
            f"Ожидаемый путь: {EXPORT_PATH}\n"
            "Положи экспорт в `.minecraft/regallactions_export.txt` или укажи `MLDSL_REGALLACTIONS_EXPORT`."
        )
    mod = load_module(TOOLS_PATH)
    lines = read_export_lines(EXPORT_PATH)

    records: list[tuple[int, dict]] = []
    chunk: list[str] = []
    rec_no = 0
    for line in lines:
        if line.startswith("# record"):
            if chunk:
                records.append((rec_no, mod.parse_record_lines(chunk)))
                chunk = []
            try:
                rec_no = int(line.split()[-1])
            except Exception:
                rec_no += 1
        elif line.startswith("records="):
            continue
        else:
            chunk.append(line)
    if chunk:
        records.append((rec_no, mod.parse_record_lines(chunk)))

    out = {
        "recordsTotal": len(records),
        "issues": [],
        "stats": {
            "hasChestTrue": 0,
            "hasChestFalse": 0,
            "issuesCount": 0,
            "issuesNoArgs": 0,
            "issuesNoSlotForGlass": 0,
        },
    }

    for no, record in records:
        if record.get("hasChest"):
            out["stats"]["hasChestTrue"] += 1
        else:
            out["stats"]["hasChestFalse"] += 1

        items: dict[int, dict] = record.get("items") or {}
        glass = [
            (slot, it)
            for slot, it in sorted(items.items())
            if it.get("id") == mod.GLASS_ID and int(it.get("meta", 0)) != 15
        ]

        if not record.get("hasChest") and not glass:
            continue

        glass_debug = []
        no_slot_count = 0
        for slot, it in glass:
            meta = int(it.get("meta", 0))
            mode = mod.determine_mode_v2(items, slot, meta, it.get("name", ""))
            if mode is None:
                continue
            cand = mod.find_candidate_slot_v2(items, slot, set(), mode)
            # Meta=0 (ANY) panes are also used as GUI "decor" around enum-switch items,
            # and we intentionally don't bind occupied neighbors for ANY mode. Treat
            # missing slot for ANY as non-fatal.
            if cand is None and mode != "ANY":
                no_slot_count += 1
            neighbors = []
            for ns in mod.neighbor_slots(slot):
                nit = items.get(ns)
                if not nit:
                    neighbors.append({"slot": ns, "empty": True})
                    continue
                neighbors.append(
                    {
                        "slot": ns,
                        "id": nit.get("id"),
                        "meta": nit.get("meta"),
                        "name": mod.strip_colors(nit.get("name", "")).strip(),
                    }
                )
            glass_debug.append(
                {
                    "glassSlot": slot,
                    "glassMeta": meta,
                    "glassName": mod.strip_colors(it.get("name", "")).strip(),
                    "mode": mode,
                    "candidateSlot": cand,
                    "neighbors": neighbors,
                }
            )

        args = mod.extract_args(record)
        enums = mod.extract_enums(record)

        issue_types = []
        if record.get("hasChest") and glass_debug and not args:
            issue_types.append("no_args_extracted")
        if no_slot_count:
            issue_types.append("glass_without_candidate_slot")

        if not issue_types:
            continue

        out["stats"]["issuesCount"] += 1
        if "no_args_extracted" in issue_types:
            out["stats"]["issuesNoArgs"] += 1
        if "glass_without_candidate_slot" in issue_types:
            out["stats"]["issuesNoSlotForGlass"] += 1

        signs = record.get("signs") or ["", "", "", ""]
        out["issues"].append(
            {
                "record": no,
                "types": issue_types,
                "hasChest": bool(record.get("hasChest")),
                "gui": mod.strip_colors(record.get("gui", "")).strip(),
                "sign1": mod.strip_colors(signs[0]).strip(),
                "sign2": mod.strip_colors(signs[1]).strip(),
                "argsExtracted": len(args),
                "enumsExtracted": len(enums),
                "glassMarkers": glass_debug,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"records={out['recordsTotal']} hasChestTrue={out['stats']['hasChestTrue']}")
    print(
        "issues={issuesCount} noArgs={issuesNoArgs} noSlot={issuesNoSlotForGlass} wrote={out}".format(
            **out["stats"], out=OUT_PATH
        )
    )
    for e in out["issues"][:30]:
        print(f"#record {e['record']}: {e['sign1']} | {e['sign2']} | gui={e['gui']} types={','.join(e['types'])}")


if __name__ == "__main__":
    main()
