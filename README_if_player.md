# Поддержка if_player в MLCT/MLDSL

## Обзор

Добавлена полная поддержка условий `if_player` (условия игрока) в компиляторе MLDSL. Теперь доступны два синтаксиса для работы с условиями игрока.

## Синтаксис

### 1. Новый синтаксис (рекомендуемый)
```mldsl
event(join) {
    if_player.issprinting() {
        player.message("Игрок бежит!")
    }
    
    if_player.hasitem("minecraft:diamond") {
        player.message("У игрока есть алмаз!")
    }
}
```

### 2. Старый синтаксис (для совместимости)
```mldsl
event(join) {
    SelectObject.player.IfPlayer.IsSprinting {
        player.message("Игрок бежит!")
    }
    
    SelectObject.player.IfPlayer.HasItem {
        player.message("У игрока есть предмет!")
    }
}
```

## Доступные функции if_player

Все функции должны вызываться в нижнем регистре (например, `issprinting()`, а не `IsSprinting()`):

| Функция | Описание | Пример |
|---------|----------|--------|
| `issprinting()` | Проверяет, бежит ли игрок | `if_player.issprinting()` |
| `issneaking()` | Проверяет, крадется ли игрок | `if_player.issneaking()` |
| `hasitem(item)` | Проверяет наличие предмета | `if_player.hasitem("minecraft:diamond")` |
| `gamemodeequals(mode)` | Проверяет режим игры | `if_player.gamemodeequals("creative")` |
| `playernameequals(name)` | Проверяет имя игрока | `if_player.playernameequals("Admin")` |
| `playermessageequals(message)` | Проверяет сообщение игрока | `if_player.playermessageequals("привет")` |
| `holdingitem(item)` | Проверяет, держит ли игрок предмет | `if_player.holdingitem("minecraft:sword")` |
| `havepermissions()` | Проверяет наличие прав | `if_player.havepermissions()` |
| `interactiontype()` | Проверяет тип взаимодействия | `if_player.interactiontype()` |
| `handusedequals()` | Проверяет используемую руку | `if_player.handusedequals()` |

## Примеры использования

### Базовые условия
```mldsl
event(join) {
    // Проверка состояния
    if_player.issprinting() {
        player.message("Ты бежишь!")
    }
    
    if_player.issneaking() {
        player.message("Ты крадешься!")
    }
    
    // Проверка предметов
    if_player.hasitem("minecraft:diamond_sword") {
        player.message("У тебя алмазный меч!")
    }
    
    // Проверка режима игры
    if_player.gamemodeequals("creative") {
        player.message("Ты в творческом режиме")
    }
}
```

### Вложенные условия
```mldsl
event(join) {
    // Комбинированные проверки
    if_player.issprinting() {
        if_player.hasitem("minecraft:elytra") {
            player.message("Бежишь с элитрами!")
        }
    }
    
    // Множественные условия
    if_player.gamemodeequals("creative") {
        if_player.havepermissions() {
            player.message("Ты творческий администратор!")
        }
    }
}
```

### Работа с событиями чата
```mldsl
event(chat) {
    // Реакция на сообщения
    if_player.playermessageequals("привет") {
        player.message("И тебе привет!")
    }
    
    if_player.playermessageequals("помощь") {
        player.message("Доступные команды: /help, /spawn")
    }
}
```

## Технические детали

### Реализация в компиляторе
1. **Парсинг**: Добавлены регулярные выражения для обоих синтаксисов
2. **Маппинг**: Функции автоматически конвертируются в нижний регистр
3. **Блоки**: Все условия `if_player` используют блок `minecraft:planks`
4. **API**: Функции добавлены в `api_aliases.json` через скрипт `tools/add_if_player_aliases.py`

### Файлы конфигурации
- `src/assets/LangTokens.json` - содержит определения функций `IF_PLAYER`
- `out/api_aliases.json` - генерируется с функциями `if_player`
- `allactions.txt` (в корне репозитория) - содержит маппинг "Если игрок" → `minecraft:planks`

### Ограничения
1. Все функции `if_player` должны вызываться в нижнем регистре
2. Условия должны находиться внутри блоков `event`, `func` или `loop`
3. Параметры функций передаются в скобках (например, `hasitem("minecraft:diamond")`)

## Обновление проекта

Если нужно добавить новые функции `if_player`:
1. Добавить функцию в `src/assets/LangTokens.json` (раздел `IF_PLAYER`)
2. Запустить `python tools/add_if_player_aliases.py`
3. Запустить `python tools/build_api_aliases.py`

## Тестирование

Для тестирования используйте файлы:
- `test_if_player_simple.mldsl` - простые примеры
- `test_if_player_complete.mldsl` - полные примеры
- `test_if_player_old.mldsl` - старый синтаксис

Компиляция:
```bash
python tools/mldsl_compile.py test_if_player_simple.mldsl --print-plan
```
