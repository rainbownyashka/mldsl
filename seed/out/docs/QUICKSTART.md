# MLCT DSL (draft)

## Events
```
event(join) {
    message(text("Hello", player))
}
```

## Assignment
```
score = num(5)
name = text(player, " joined")
```

## Action args
- Action and arg aliases live in `out/action_aliases.json`.
- GUI slots are mapped from `out/actions_catalog.json`.

## Enum switches
- Enum items are detected by lore lines with filled/empty bullets.
- Use `clicks(slot,n)` in `/placeadvanced`.

## /placeadvanced example
```
/placeadvanced diamond_block "vhod" no iron_block "Obedinit texty" "slot(13)=var_save(setswa),slot(27)=TEXT1,slot(28)=TEXT2,clicks(22,2)=0"
```
