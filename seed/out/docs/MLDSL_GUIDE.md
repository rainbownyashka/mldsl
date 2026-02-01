# MLDSL Guide (generated)

This is a short "how the compiler thinks" guide for people and for AI agents generating `.mldsl`.
The action catalog comes from `out/api_aliases.json`.

## Build pipeline

- `python tools/build_all.py`
  - Builds `out/actions_catalog.json`
  - Builds `out/api_aliases.json`
  - Generates docs into `out/docs`

## Basic syntax

### Events

```
event(join) {
    player.message("Hello!")
}
```

### Functions

Supported keywords: `func`, `function`, `def`, `функция`.
Both `func hello {}` and `func(hello) {}` are accepted.

```
func hello {
    player.message("Hi")
}
```

### Cycles / loops

```
loop mycycle every 5 {
    player.message("tick")
}
```

### Calling actions

API calls are `module.func(args...)`. Arguments can be positional or `key=value`
depending on the function’s `params` (see per-function docs).

```
player.message("text1", "text2")
if_player.сообщение_равно("!ping") {
    player.message("pong")
}
```

### Calling a function by name

```
hello()
call(hello)             # sync by default
call(hello, async=true) # async/sync is enum inside the GUI
```

### Variables and assignment

Variable names may contain placeholders, e.g. `%selected%counter`.

- Normal variable: `var(name)`
- Saved variable: `var_save(name)`

Assignment sugar compiles into variable actions (`var.set_value`, etc):

```
a = 1
save a = 1
a ~ 1               # shorthand for save a = 1
%selected%counter = %selected%counter + 1
```

Numeric expressions are limited to `+ - * /` with constants and names (no nested calls).
If an expression needs multiple server actions, compiler prints a warning about extra actions.

### `if` conditions

Examples:

```
if %selected%counter < 2 {
    player.message("low")
}

ifexists(%player%flag) {
    player.message("exists")
}

iftext "a" in "abc" {
    player.message("ok")
}
```

### Enums (switchers)

Some actions have enum switchers (lore bullets) and are represented in docs as `enums`.
You can usually pass the enum by name (generated enum name from docs) as `key=value`
and the compiler converts it to `clicks(slot,n)=0`.

## Output model (what compiler produces)

The compiler produces a linear plan of entries like:

```
{ "block": "diamond_block", "name": "вход", "args": "no" }
{ "block": "cobblestone", "name": "Отправить сообщение||Сообщение", "args": "slot(9)=text(hi)" }
{ "block": "newline" }
```

This plan is executed by the mod using the existing `/placeadvanced` mechanism.

## Important limitations (server constraints)

- `/placeadvanced` has a command length limit (~240 chars).
- Some bulk calls are chunked by the compiler (18 names per action).
