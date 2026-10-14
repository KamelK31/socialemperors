"""Shared helpers for game command handlers (command.py and handlers_*.py)."""
import json

from get_game_config import get_game_config, get_attribute_from_item_id, get_name_from_item_id
from engine import timestamp_now

def town(save: dict, town_id) -> dict:
    "The map (island) with this id. Falls back to the first map if the id is unknown."
    try:
        return save["maps"][int(town_id)]
    except (ValueError, TypeError, IndexError):
        return save["maps"][0]

def item_attr(item_id, attribute, default=None):
    "An attribute of an item from the game config (cost, cost_type, xp, name...)."
    try:
        value = get_attribute_from_item_id(int(item_id), attribute)
    except Exception:
        return default
    return default if value is None else value

def item_name(item_id) -> str:
    try:
        return str(get_name_from_item_id(int(item_id)))
    except Exception:
        return f"item {item_id}"

# --- resources ---------------------------------------------------------------

RESOURCE_KEYS = {"g": "coins", "w": "wood", "s": "stone", "f": "food"}

def add_resource(save: dict, map: dict, cost_type: str, amount) -> None:
    "Adds (or removes, if negative) gold 'g', wood 'w', stone 's', food 'f', cash 'c' or xp 'x'. Never goes below 0."
    amount = int(amount)
    if cost_type == "c":
        save["playerInfo"]["cash"] = max(int(save["playerInfo"]["cash"]) + amount, 0)
    elif cost_type == "x":
        map["xp"] = max(int(map["xp"]) + amount, 0)
    elif cost_type in RESOURCE_KEYS:
        key = RESOURCE_KEYS[cost_type]
        map[key] = max(int(map.get(key, 0)) + amount, 0)

def spend(save: dict, map: dict, cost_type: str, amount) -> None:
    add_resource(save, map, cost_type, -int(amount))

def spend_cash(save: dict, amount) -> None:
    save["playerInfo"]["cash"] = max(int(save["playerInfo"]["cash"]) - int(amount), 0)

# --- map items ---------------------------------------------------------------
# A map item is a list: [item_id, x, y, orientation, collected_at_timestamp, level, (optional) [units inside]]

def find_map_item(map: dict, x, y, item_id=None):
    "The item at (x, y) (optionally with this id), or None."
    for item in map["items"]:
        if item[1] == x and item[2] == y and (item_id is None or item[0] == item_id):
            return item
    return None

def add_map_item(map: dict, item_id, x, y, orientation=0, level=0) -> list:
    item = [item_id, x, y, orientation, timestamp_now(), level]
    map["items"].append(item)
    return item

def _remove_map_item(map: dict, item_id, x, y) -> bool:
    for item in map["items"]:
        if item[0] == item_id and item[1] == x and item[2] == y:
            map["items"].remove(item)
            return True
    return False

# --- inventories -------------------------------------------------------------
# Gifts: privateState["gifts"] = list, index = item id, value = count.
# Stored items: map["store"] = {"item_id": count}.

def _store(map: dict) -> dict:
    "Items stored in the map's inventory (not gifts). The game reads it as map.store = {item_id: count}."
    store = map.get("store")
    if not isinstance(store, dict):
        store = {}
        map["store"] = store
    return store

def _store_add(map: dict, item_id, count: int = 1) -> None:
    store = _store(map)
    key = str(item_id)
    store[key] = int(store.get(key, 0)) + count

def _store_take(map: dict, item_id) -> bool:
    "Removes one item from the stored inventory. Returns False if there was none."
    store = _store(map)
    key = str(item_id)
    if int(store.get(key, 0)) <= 0:
        return False
    store[key] = int(store[key]) - 1
    if store[key] <= 0:
        del store[key]
    return True

def _gift_take(save: dict, item_id) -> bool:
    "Removes one item from the gifts inventory. Returns False if there was none."
    gifts = save["privateState"]["gifts"]
    if not (isinstance(item_id, int) and 0 <= item_id < len(gifts) and gifts[item_id] > 0):
        return False
    gifts[item_id] -= 1
    while len(gifts) != 0 and gifts[-1] == 0:
        gifts.pop()
    return True

def _remove_map_item(map: dict, item_id, x, y) -> bool:
    for item in map["items"]:
        if item[0] == item_id and item[1] == x and item[2] == y:
            map["items"].remove(item)
            return True
    return False


def _gift_add(save: dict, item_id, count: int = 1) -> None:
    gifts = save["privateState"]["gifts"]
    item_id = int(item_id)
    while len(gifts) <= item_id:
        gifts.append(0)
    gifts[item_id] += count

def json_arg(value):
    "Some args are JSON strings, some are already decoded."
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value

def private(save: dict, key: str, default):
    "privateState[key], created with `default` if missing."
    ps = save["privateState"]
    if key not in ps:
        ps[key] = default
    return ps[key]
