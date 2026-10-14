"""Building, storage and collection commands: mill timers (activate), upgrades, early unlocks, map
skins, population wonder, graveyard, sacrifice altar, units bought with cash, mobile (iPhone) box,
second island, unit warehouse, collections and a few admin/debug commands.

Every rule here mirrors what the Flash client does locally when it sends the command (the
ActionScript file is named in each handler), and stores the result exactly where the client reads
it back at login, so that the save matches what the player saw once they reconnect.
"""
import copy
import json
import math
import os
import random

from cmd_helpers import (town, item_attr, item_name, add_resource, spend, spend_cash,
                         find_map_item, add_map_item, _remove_map_item, _store_add, _store_take,
                         _gift_add, _gift_take, json_arg, private)
from engine import timestamp_now
from get_game_config import get_game_config

# --- client constants (core/Config.as, core/Constants.as) ---------------------

MAP_WIDTH = 100                 # Config.EI_MAP_WIDTH
MAP_HEIGHT = 100                # Config.EI_MAP_HEIGHT
COLLECT_MINUTES = [5, 60, 240, 480]  # Config.COLLECT_MINUTES (mill timer choices, cp = index + 1)
MULTIPLIER_UNLOCK = 1 / 3       # Config.MULTIPLIER_UNLOCK
DIVISOR_SELL = 20               # Config.DIVISOR_SELL
TOWN_PRICE_GOLD = 100000        # Config.TOWN_PRICE_GOLD
TOWN_PRICE_CASH = 22            # Config.TOWN_PRICE_CASH
ID_BUILDING_DOCK = 224
ID_BUILDING_ZEPPELIN_TOWER = 299
ID_TOWN_HALL = 26
ID_TROLL_HALL = 289
NUM_COLLECTIONS = 23            # CollectableManager.NUM_COLLECTIONS
# CollectableManager.arCollections[i][0]: the item given when collection i is completed
COLLECTION_REWARDS = [0, 176, 177, 178, 179, 180, 551, 546, 544, 552, 553, 206, 207, 208, 209,
                      124, 561, 562, 563, 564, 565, 875, 853, 1410]
# Items that are not IsoFightingElement on the client (IsoEngine element factory): terrain,
# graveyard, special collection. Everything else is killed by MapInitializer.cleanAllMapTiles.
NON_FIGHTING_SUBCATS = {6, 1411, 1611}

# --- small helpers -----------------------------------------------------------

def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

def _bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)

def _globals() -> dict:
    return get_game_config().get("globals", {})

def _map0(save: dict) -> dict:
    "XP lives in maps[0] (the map sent at login, also what level up / publish score update)."
    return save["maps"][0]

def _add_xp(save: dict, amount) -> None:
    amount = _int(amount)
    if amount:
        add_resource(save, _map0(save), "x", amount)

def _item_attrs(item: list) -> dict:
    "The attributes dict of a map item (index 7), created if missing. The client reads it as loaded.attrs."
    while len(item) < 6:
        item.append(0)
    if len(item) < 7:
        item.append([])
    elif not isinstance(item[6], list):
        item[6] = []
    if len(item) < 8:
        item.append({})
    elif not isinstance(item[7], dict):
        item[7] = {}
    return item[7]

def _find_building(map: dict, x, y, item_id=None):
    item = find_map_item(map, _int(x), _int(y), _int(item_id) if item_id is not None else None)
    if item is None and item_id is not None:
        item = find_map_item(map, _int(x), _int(y))
    return item

def _private_dict(save: dict, key: str) -> dict:
    "privateState[key] as a dict {str(id): value}. Old saves may hold [] (or a list of ids)."
    value = private(save, key, {})
    if not isinstance(value, dict):
        value = {str(v): True for v in value} if isinstance(value, list) else {}
        save["privateState"][key] = value
    return value

def _private_list(save: dict, key: str) -> list:
    value = private(save, key, [])
    if not isinstance(value, list):
        value = list(value.keys()) if isinstance(value, dict) else []
        save["privateState"][key] = value
    return value

def _in_map(x, y) -> bool:
    return isinstance(x, (int, float)) and isinstance(y, (int, float)) \
        and float(x).is_integer() and float(y).is_integer() \
        and 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT

def _unit_collection_units() -> set:
    units = set()
    for cat in get_game_config().get("units_collections_categories", {}).values():
        for u in cat.get("units", []) or []:
            units.add(_int(u))
    return units

def _mark_bought_unit(save: dict, unit_id) -> None:
    "privateState.boughtUnits: units that count for the unit collections (UnitCollectionsManager.addUnit)."
    unit_id = _int(unit_id)
    if unit_id not in _unit_collection_units():
        return
    bought = _private_list(save, "boughtUnits")
    if unit_id not in bought:
        bought.append(unit_id)

def _warehouse(map: dict) -> dict:
    "map.warehousedUnits = {unit_id: count} (Base.as reads it at login)."
    units = map.get("warehousedUnits")
    if not isinstance(units, dict):
        units = {}
        map["warehousedUnits"] = units
    return units

def _sell_refund(item_id) -> tuple:
    "What the client gives back when selling an item from the inventory (GiftButtonLarge.sellGift)."
    cost_type = item_attr(item_id, "cost_type", "")
    if cost_type == "c" or _int(item_id) in (ID_BUILDING_DOCK, ID_BUILDING_ZEPPELIN_TOWER):
        return cost_type, 0  # Config.SELL_FOR_ZERO_CASH
    return cost_type, _int(item_attr(item_id, "cost", 0)) // DIVISOR_SELL

# --- buildings ----------------------------------------------------------------

def activate(save, args):
    # popups/PopupCollect.as setShit/resetShit: [x, y, townID, building_id, cp]
    # cp = chosen collect time (index + 1 in Config.COLLECT_MINUTES), 0 = reset after collecting.
    # The client keeps it in loaded.attrs.cp (map item index 7) and starts the timer now.
    x, y, town_id, building_id, cp = args[0], args[1], args[2], args[3], _int(args[4])
    if not 0 <= cp <= len(COLLECT_MINUTES):
        raise ValueError(f"bad collect time {cp}")
    map = town(save, town_id)
    item = _find_building(map, x, y, building_id)
    if item is None:
        print("Activate:", item_name(building_id), f"not found at ({x},{y})")
        return
    _item_attrs(item)["cp"] = cp
    if cp > 0:
        item[4] = timestamp_now()  # collected_at: the client shows the timer from 0
        print("Activate", item_name(item[0]), f"at ({x},{y}) for", COLLECT_MINUTES[cp - 1], "min")
    else:
        print("Activate", item_name(item[0]), f"at ({x},{y}) reset")

def upgrade(save, args):
    # core/isoengine/IsoInteractiveElement.as doUpgrade: [x, y, townID], no cost, ++uiLevel.
    # (Dead code in this client: real upgrades are sent as sell 'UPGR' + buy of the next item.)
    x, y, town_id = args[0], args[1], args[2]
    map = town(save, town_id)
    item = _find_building(map, x, y)
    if item is None:
        print("Upgrade: nothing at", f"({x},{y})")
        return
    while len(item) < 6:
        item.append(0)
    item[5] = _int(item[5]) + 1
    # privateState.lastUpgrades: timestamps, the client counts today's ones (numUpgradesToday)
    now = timestamp_now()
    upgrades = [t for t in _private_list(save, "lastUpgrades") if _int(t) > now - 2 * 86400]
    upgrades.append(now)
    save["privateState"]["lastUpgrades"] = upgrades
    print("Upgrade", item_name(item[0]), f"at ({x},{y}) to level", item[5])

def unlock_building(save, args):
    # popups/PopupUnlockBuilding.as: unlock an item before its level for ceil(min_level / 3) cash
    item_id = _int(args[0])
    unlocked = _private_dict(save, "unlockedEarlyBuildings")
    if unlocked.get(str(item_id)):
        print("Unlock early", item_name(item_id), ": already unlocked")
        return
    min_level = _int(item_attr(item_id, "min_level", 0))
    price = int(math.ceil(min_level * MULTIPLIER_UNLOCK))
    spend_cash(save, price)
    unlocked[str(item_id)] = True
    print("Unlock early", item_name(item_id), "for", price, "cash")

def unlock_skin(save, args):
    # popups/PopupWeather.as onUnlock: globals.COST_UNLOCK_SKIN cash -> privateState.unlockedSkins[id]
    skin_id = str(_int(args[0]))
    unlocked = _private_dict(save, "unlockedSkins")
    if unlocked.get(skin_id):
        print("Unlock skin", skin_id, ": already unlocked")
        return
    price = _int(_globals().get("COST_UNLOCK_SKIN", 20))
    spend_cash(save, price)
    unlocked[skin_id] = True
    print("Unlock skin", skin_id, "for", price, "cash")

def set_skin(save, args):
    # popups/PopupWeather.as: [townID, skin_id] -> map.skin (Player.skinMap)
    map = town(save, args[0])
    map["skin"] = _int(args[1])
    print("Map skin set to", map["skin"])

def increase_population(save, args):
    # popups/PopupRecruitmentPopulation.as onRecruitComplete: ++map.increasedPopulation
    # (+globals.POPULATION_INCREASE each, at most globals.POPULATION_INCREASE_QTY times)
    map = town(save, args[0] if args else 0)
    qty = _int(_globals().get("POPULATION_INCREASE_QTY", 5))
    map["increasedPopulation"] = min(_int(map.get("increasedPopulation", 0)) + 1, qty)
    print("Population limit increased:", map["increasedPopulation"], "/", qty)

def clear_tiles_area(save, args):
    # core/MapInitializer.as cleanAllMapTiles (admin panel): every unit/building is removed
    # client side without sell commands, then [townID, x1, y1, x2, y2, ""].
    map = town(save, args[0])
    x1, y1, x2, y2 = (_int(a) for a in args[1:5])
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)
    kept, removed = [], 0
    for item in map["items"]:
        inside = x1 <= _int(item[1]) <= x2 and y1 <= _int(item[2]) <= y2
        subcat = _int(item_attr(item[0], "subcat_functional", -1), -1)
        known = item_attr(item[0], "type") is not None
        if inside and known and subcat not in NON_FIGHTING_SUBCATS:
            removed += 1
        else:
            kept.append(item)
    map["items"] = kept
    print(f"Cleared area ({x1},{y1})-({x2},{y2}):", removed, "items removed")

def pop_sell(save, args):
    # core/isoengine/IsoBuilding.as PopSell (sacrifice altar): [bx, by, townID, building_id, unit_id]
    # The unit inside the building is destroyed; for gold units the client drops a gold token worth
    # floor(cost / DIVISOR_SELL) (core/isoengine/IsoElement.as), added when clicked.
    bx, by, town_id, building_id, unit_id = args[0], args[1], args[2], args[3], _int(args[4])
    map = town(save, town_id)
    building = _find_building(map, bx, by, building_id)
    if building is None or len(building) < 7 or not isinstance(building[6], list) or unit_id not in building[6]:
        print("Sacrifice:", item_name(unit_id), "not found in building at", f"({bx},{by})")
        return
    building[6].remove(unit_id)
    gold = 0
    if item_attr(unit_id, "cost_type") == "g":
        gold = _int(item_attr(unit_id, "cost", 0)) // DIVISOR_SELL
        add_resource(save, map, "g", gold)
    print("Sacrifice", item_name(unit_id), f"+{gold} gold")

def fast_forward(save, args):
    # GUI/AdminPanel.as (debug): [seconds]. Moves every timer of the save back in time.
    seconds = _int(args[0])
    if seconds <= 0:
        print("Fast forward: nothing to do")
        return
    for map in save["maps"]:
        for item in map["items"]:
            if len(item) > 4 and _int(item[4]) > 0:
                item[4] = max(_int(item[4]) - seconds, 1)
        if _int(map.get("timestampLastTreasure", 0)) > 0:
            map["timestampLastTreasure"] = max(_int(map["timestampLastTreasure"]) - seconds, 1)
    ps = save["privateState"]
    for key in ("timeStampTakeCare", "timeStampTakeCareMonster", "riderTimeStamp"):
        if _int(ps.get(key, -1)) > 0:
            ps[key] = max(_int(ps[key]) - seconds, 1)
    print("Fast forward", seconds, "seconds")

def gold_statue_conversion(save, args):
    # core/isoengine/isounits/IsoGoldenDynastyDragon.as: an enemy turned into a gold statue drops
    # a gold token of GOLD_PER_STATUE (10). No town id: the player's main island.
    gold = _int(args[0])
    if not 0 <= gold <= 1000:
        raise ValueError(f"bad gold amount {gold}")
    add_resource(save, _map0(save), "g", gold)
    print("Gold statue: +", gold, "gold", sep='')

def buy_cash(save, args):
    # Unit paid with cash (IsoBuilding training, PopupHeroes altar): [id, x, y, frame, townID]
    # The client takes item.cost_unit_cash cash and gives item.xp. If there is no altar, the hero
    # goes to the inventory (sent just before as store_add_items) and x, y are the popup screen
    # position (outside the 100x100 map): the unit is then not placed.
    unit_id, x, y, town_id = _int(args[0]), args[1], args[2], args[4] if len(args) > 4 else 0
    map = town(save, town_id)
    price = _int(item_attr(unit_id, "cost_unit_cash", 0))
    spend_cash(save, price)
    _add_xp(save, item_attr(unit_id, "xp", 0))
    if _in_map(x, y):
        add_map_item(map, unit_id, int(x), int(y))
        where = f"at ({int(x)},{int(y)})"
    else:
        where = "(to inventory)"
    _mark_bought_unit(save, unit_id)
    print("Buy", item_name(unit_id), "for", price, "cash", where)

def buy_stored_item_cash(save, args):
    # popups/PopupAllUnits.as buyUnit: [townID, item_id, cash] -> inventory, counts as bought
    map = town(save, args[0])
    item_id, price = _int(args[1]), _int(args[2])
    if price < 0:
        raise ValueError("negative price")
    spend_cash(save, price)
    _store_add(map, item_id)
    _mark_bought_unit(save, item_id)
    print("Buy", item_name(item_id), "to inventory for", price, "cash")

# --- mobile (iPhone) box: privateState.iphoneBox = {box_id: [item_id, ...]} ---------------

def _iphone_take(save: dict, item_id: int) -> bool:
    box = save["privateState"].get("iphoneBox")
    if isinstance(box, dict):
        for key, value in list(box.items()):
            entry = value[0] if isinstance(value, list) and value else value
            if _int(entry, -1) == item_id:
                del box[key]
                return True
    elif isinstance(box, list):
        for i, value in enumerate(box):
            entry = value[0] if isinstance(value, list) and value else value
            if _int(entry, -1) == item_id:
                box.pop(i)
                return True
    return False

def place_iphone(save, args):
    # core/Base.as sendPlaceItemCmd: [item_id, x, y, frame, townID] (no xp for mobile items)
    item_id, x, y = _int(args[0]), _int(args[1]), _int(args[2])
    map = town(save, args[4] if len(args) > 4 else 0)
    if not _iphone_take(save, item_id):
        print("Place mobile item", item_name(item_id), ": not in the mobile box, placed anyway")
    add_map_item(map, item_id, x, y)
    _mark_bought_unit(save, item_id)
    print("Place mobile item", item_name(item_id), f"at ({x},{y})")

def sell_iphone_item(save, args):
    # GUI/GiftButtonLarge.as sellGift: [item_id, townID], refund floor(cost / 20) (nothing for cash items)
    item_id = _int(args[0])
    map = town(save, args[1] if len(args) > 1 else 0)
    if not _iphone_take(save, item_id):
        print("Sell mobile item", item_name(item_id), ": not in the mobile box, ignored")
        return
    cost_type, refund = _sell_refund(item_id)
    add_resource(save, map, cost_type, refund)
    print("Sell mobile item", item_name(item_id), f"+{refund} {cost_type}")

# --- islands -----------------------------------------------------------------------------

def _initial_village() -> dict:
    from bundle import VILLAGES_DIR
    with open(os.path.join(VILLAGES_DIR, "initial.json"), encoding="utf-8") as f:
        return json.load(f)

def _new_town_map(save: dict, town_id: int, race: str) -> dict:
    "A fresh island built from villages/initial.json; a troll island gets a Troll Hall."
    new = copy.deepcopy(_initial_village()["maps"][0])
    new["id"] = town_id
    new["race"] = race
    new["timestamp"] = timestamp_now()
    new["xp"] = _map0(save).get("xp", new["xp"])  # the level is shared: keep the player's
    new["level"] = _map0(save).get("level", new["level"])
    new["store"] = {}
    if race != "h":
        items = []
        for item in new["items"]:
            if item[0] == ID_TOWN_HALL:
                items.append([ID_TROLL_HALL] + item[1:])
            elif item_attr(item[0], "race") == "n":
                items.append(item)
        new["items"] = items
    for item in new["items"]:
        item[4] = timestamp_now()
    return new

def buy_map(save, args):
    # popups/PopupRaceSelector.as onUnlockCash/onUnlockGold: [new_town_id (1), 1 = cash / 0 = gold,
    # race, townID], Config.TOWN_PRICE_CASH (22) cash or TOWN_PRICE_GOLD (100000) gold, then the
    # client travels to the new town: it asks get_player_info with user=<self>&map=1, which the
    # server answers with maps[1]. TownManager reads privateState.maps[i].r (race of each town).
    new_id = _int(args[0], -1)
    paid_cash = _bool(args[1])
    race = args[2] if args[2] in ("h", "t") else "t"
    current = town(save, args[3] if len(args) > 3 else 0)
    maps = save["maps"]
    if not 1 <= new_id <= len(maps):
        raise ValueError(f"bad town id {new_id}")
    if paid_cash:
        spend_cash(save, TOWN_PRICE_CASH)
    else:
        spend(save, current, "g", TOWN_PRICE_GOLD)
    if new_id == len(maps):
        maps.append(_new_town_map(save, new_id, race))
        created = "created"
    else:
        created = "already owned"
    pi = save["playerInfo"]
    names = pi.setdefault("map_names", [])
    while len(names) <= new_id:
        names.append("Troll Empire" if race == "t" else "My Empire")
    sizes = pi.setdefault("map_sizes", [])
    while len(sizes) <= new_id:
        sizes.append(0)
    towns = private(save, "maps", [])
    if not isinstance(towns, list):
        towns = []
        save["privateState"]["maps"] = towns
    while len(towns) <= new_id:
        towns.append({"r": maps[len(towns)].get("race", "h")})
    towns[new_id]["r"] = maps[new_id].get("race", race)
    print("Buy island", new_id, f"({race})", "for", f"{TOWN_PRICE_CASH} cash" if paid_cash else f"{TOWN_PRICE_GOLD} gold", "-", created)

def _slot(args) -> str:
    # The admin console sends "args": "<id>" (a string), the buttons send [id]
    value = args[0] if isinstance(args, list) and args else args
    return str(_int(value, -1))

def save_map(save, args):
    # GUI/AdminPanel.as (debug): save the layout of the main island in slot <id>
    slot = _slot(args)
    map = _map0(save)
    slots = save.setdefault("debugSavedMaps", {})
    slots[slot] = {"items": copy.deepcopy(map["items"]), "expansions": copy.deepcopy(map.get("expansions", []))}
    print("Map layout saved in slot", slot, f"({len(map['items'])} items)")

def load_map(save, args):
    # GUI/AdminPanel.as (debug): restore the layout saved in slot <id> (items and expansions only)
    slot = _slot(args)
    saved = save.get("debugSavedMaps", {}).get(slot)
    if not isinstance(saved, dict) or not isinstance(saved.get("items"), list):
        print("No map layout in slot", slot)
        return
    map = _map0(save)
    map["items"] = copy.deepcopy(saved["items"])
    map["expansions"] = copy.deepcopy(saved.get("expansions", map.get("expansions", [])))
    print("Map layout loaded from slot", slot, f"({len(map['items'])} items)")

def reset(save, args):
    # GUI/AdminPanel.as onReset (debug): the village goes back to a new game (villages/initial.json).
    # The previous save is kept as a dated backup in saves/backups/<USERID>/.
    pid = save["playerInfo"]["pid"]
    try:
        from sessions import backup_session
        backup_session(str(pid), force=True)
    except Exception as e:
        print(f"(backup failed: {e}) ", end='')
    new = copy.deepcopy(_initial_village())
    new["version"] = save.get("version", new.get("version"))
    new["playerInfo"]["pid"] = pid
    new["playerInfo"]["name"] = save["playerInfo"].get("name", new["playerInfo"]["name"])
    new["playerInfo"]["pic"] = save["playerInfo"].get("pic", new["playerInfo"]["pic"])
    new["maps"][0]["timestamp"] = timestamp_now()
    new["privateState"]["dartsRandomSeed"] = abs(int((2**16 - 1) * random.random()))
    save.clear()
    save.update(new)
    print("Village RESET to a new game (old save backed up)")

# --- inventory / warehouse ----------------------------------------------------------------

def add_items_store(save, args):
    # popups/PopupArabicDeals.as onBuy: [json([unit ids]), cash] -> inventory
    ids = json_arg(args[0])
    if not isinstance(ids, list):
        raise ValueError("bad item list")
    ids = [_int(i) for i in ids]
    price = _int(args[1]) if len(args) > 1 else 0
    if price < 0:
        raise ValueError("negative price")
    map = _map0(save) if len(args) < 3 else town(save, args[2])
    spend_cash(save, price)
    for item_id in ids:
        _store_add(map, item_id)
    print("Offer bought for", price, "cash:", ", ".join(item_name(i) for i in ids))

def add_unit_warehouse(save, args):
    # core/isoengine/IsoBuilding.as pushUnitToWarehause: [x, y, townID, unit_id]
    x, y, town_id, unit_id = _int(args[0]), _int(args[1]), args[2], _int(args[3])
    map = town(save, town_id)
    if not _remove_map_item(map, unit_id, x, y):
        print("Warehouse:", item_name(unit_id), f"not found at ({x},{y}), stored anyway. ", end='')
    units = _warehouse(map)
    units[str(unit_id)] = _int(units.get(str(unit_id), 0)) + 1
    print("Unit", item_name(unit_id), "put in the warehouse")

def place_warehoused_item(save, args):
    # popups/PopupUnitWarehouse.as: [unit_id, x, y, 0, townID]
    unit_id, x, y = _int(args[0]), _int(args[1]), _int(args[2])
    map = town(save, args[4] if len(args) > 4 else 0)
    units = _warehouse(map)
    key = str(unit_id)
    if _int(units.get(key, 0)) <= 0:
        print("Warehouse:", item_name(unit_id), "not in the warehouse, ignored")
        return
    units[key] = _int(units[key]) - 1
    if units[key] <= 0:
        del units[key]
    add_map_item(map, unit_id, x, y)
    _mark_bought_unit(save, unit_id)
    print("Unit", item_name(unit_id), f"taken out of the warehouse at ({x},{y})")

def reset_warehouse(save, args):
    # core/Base.as storeItem / AdminPanel: the warehouse building was stored or sold, every unit
    # inside goes to the inventory (client side, without other command).
    map = town(save, args[0] if args else 0)
    units = _warehouse(map)
    moved = 0
    for key, count in list(units.items()):
        count = _int(count)
        if count > 0 and _int(key, -1) >= 0:
            _store_add(map, _int(key), count)
            moved += count
    map["warehousedUnits"] = {}
    print("Warehouse emptied:", moved, "units moved to the inventory")

def buy_warehouse_capacity_single(save, args):
    # popups/PopupUnitWarehouse.as onBuyMoreSlots: globals.WAREHOUSE_CAPACITY_INCREASE_PRICE_SINGLE
    # cash, ++capacity. The client reads the whole capacity from map.warehouseAditionalCapacitySingle.
    map = town(save, args[0] if args else 0)
    g = _globals()
    price = _int(g.get("WAREHOUSE_CAPACITY_INCREASE_PRICE_SINGLE", 2))
    max_capacity = _int(g.get("WAREHOUSE_MAX_CAPACITY", 1000))
    capacity = _int(map.get("warehouseAditionalCapacitySingle", 0))
    if capacity >= max_capacity:
        print("Warehouse already at max capacity", capacity)
        return
    spend_cash(save, price)
    map["warehouseAditionalCapacitySingle"] = capacity + 1
    print("Warehouse capacity", capacity + 1, "for", price, "cash")

# --- collections -------------------------------------------------------------------------

def _collections(save: dict) -> list:
    "privateState.collections[i] = [completed 0/1, count of piece 1..5] (Base.as, CollectableManager)."
    cols = private(save, "collections", [])
    if not isinstance(cols, list):
        cols = []
        save["privateState"]["collections"] = cols
    while len(cols) <= NUM_COLLECTIONS:
        cols.append([0, 0, 0, 0, 0, 0])
    for i, col in enumerate(cols):
        if not isinstance(col, list):
            cols[i] = col = [0, 0, 0, 0, 0, 0]
        while len(col) < 6:
            col.append(0)
    return cols

def finish_collection(save, args):
    # popups/popupCollections.as: [col] (exchange the 5 pieces) or [col, 1, cash] (buy it).
    # CollectableManager.getReward: reward item to the inventory, completed flag, every piece -1.
    col = _int(args[0], -1)
    if not 1 <= col <= NUM_COLLECTIONS:
        raise ValueError(f"bad collection {col}")
    price = 0
    if len(args) > 2 and _bool(args[1]):
        price = _int(args[2])
        if price < 0:
            raise ValueError("negative price")
        spend_cash(save, price)
    collection = _collections(save)[col]
    collection[0] = 1
    for i in range(1, 6):
        if _int(collection[i]) > 0:
            collection[i] = _int(collection[i]) - 1
    rewards = _globals().get("COLLECTION_REWARDS", COLLECTION_REWARDS)
    reward = _int(rewards[col]) if col < len(rewards) else COLLECTION_REWARDS[col]
    _store_add(_map0(save), reward)
    _private_list(save, "collectionsCompleted").append(col)
    print("Collection", col, "completed" + (f" for {price} cash" if price else "") + ", reward:", item_name(reward))

def unit_collections_completed(save, args):
    # popups/PopupAllUnits.as getCollectionReward: [category_id], +1 cash, and the popup announces
    # the category reward unit (units_collections_categories[cat].rewards) -> inventory.
    cat = _int(args[0], -1)
    completed = _private_list(save, "unitCollectionsCompleted")
    if cat in completed:
        print("Unit collection", cat, "already rewarded")
        return
    completed.append(cat)
    add_resource(save, _map0(save), "c", 1)
    category = get_game_config().get("units_collections_categories", {}).get(str(cat))
    reward = _int(category.get("rewards"), 0) if isinstance(category, dict) else 0
    if reward > 0:
        _store_add(_map0(save), reward)
    print("Unit collection", cat, "completed: +1 cash", ("+ " + item_name(reward)) if reward else "")

def reset_completed_missions(save, args):
    # managers/MissionsManager.as resetGoals (debug console)
    save["privateState"]["completedMissions"] = []
    print("Completed missions reset")

def rt_publish_achievement_unit(save, args):
    # core/isoengine/IsoEngine.as: first time a unit with an achievement is on the map,
    # the client adds it to privateState.achievedUnits (and would post on Facebook).
    unit_id = _int(args[0])
    achieved = _private_list(save, "achievedUnits")
    if unit_id not in achieved:
        achieved.append(unit_id)
    print("Achievement unit", item_name(unit_id))

def put_graveyard(save, args):
    # core/isoengine/delegates/PhoenixEggDelegate.as: the phoenix egg died, the phoenix goes to the
    # graveyard. The client reads privateState.deadHeroes = {unit_id: count} (heroes and other units).
    unit_id = _int(args[0])
    dead = _private_dict(save, "deadHeroes")
    dead[str(unit_id)] = _int(dead.get(str(unit_id), 0)) + 1
    print(item_name(unit_id), "put in the graveyard")

HANDLERS = {
    "activate": activate,
    "upgrade": upgrade,
    "unlock_building": unlock_building,
    "unlock_skin": unlock_skin,
    "set_skin": set_skin,
    "increase_population": increase_population,
    "clear_tiles_area": clear_tiles_area,
    "put_graveyard": put_graveyard,
    "pop_sell": pop_sell,
    "fast_forward": fast_forward,
    "gold_statue_conversion": gold_statue_conversion,
    "buy_cash": buy_cash,
    "buy_stored_item_cash": buy_stored_item_cash,
    "place_iphone": place_iphone,
    "sell_iphone_item": sell_iphone_item,
    "buy_map": buy_map,
    "load_map": load_map,
    "save_map": save_map,
    "reset": reset,
    "add_items_store": add_items_store,
    "add_unit_warehouse": add_unit_warehouse,
    "place_warehoused_item": place_warehoused_item,
    "reset_warehouse": reset_warehouse,
    "buy_warehouse_capacity_single": buy_warehouse_capacity_single,
    "finish_collection": finish_collection,
    "unit_collections_completed": unit_collections_completed,
    "reset_completed_missions": reset_completed_missions,
    "rt_publish_achievement_unit": rt_publish_achievement_unit,
}
