"""Economy commands: market trades, magic and mana, darts, offer packs, the Bahamut Supreme
Invocation Temple, social buildings (allies "si" helpers), client flags and admin variables.

Every rule here mirrors what the Flash client does locally when it sends the command
(see the ActionScript file named in each handler), so that the save matches what the
player saw once they reconnect.
"""
import math

from cmd_helpers import (town, item_attr, item_name, add_resource, spend, spend_cash,
                         find_map_item, _store_add, json_arg, private)
from engine import timestamp_now
from get_game_config import get_game_config

# --- small helpers -----------------------------------------------------------

def _as_round(x: float) -> int:
    "ActionScript Math.round: rounds .5 up (also for negatives)."
    return int(math.floor(x + 0.5))

def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _bool(value) -> bool:
    "Flash sends booleans as true/false, 1/0 or 'true'/'false' depending on the call."
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)

def _globals() -> dict:
    return get_game_config().get("globals", {})

def _map0(save: dict) -> dict:
    "XP and level live in maps[0]: it is the map sent at login (and what level up / publish score update)."
    return save["maps"][0]

def _add_mana(save: dict, amount) -> None:
    ps = save["privateState"]
    ps["mana"] = max(_int(ps.get("mana", 0)) + int(amount), 0)

def _add(save: dict, map: dict, cost_type: str, amount) -> None:
    "add_resource that also knows mana 'm', and keeps xp in maps[0]."
    amount = int(amount)
    if amount == 0:
        return
    if cost_type == "m":
        _add_mana(save, amount)
    elif cost_type == "x":
        add_resource(save, _map0(save), "x", amount)
    else:
        add_resource(save, map, cost_type, amount)

def _magics(save: dict) -> dict:
    "privateState.magics = {spell_id: number of casts}. Older saves may hold a list."
    magics = private(save, "magics", {})
    if not isinstance(magics, dict):
        magics = {}
        save["privateState"]["magics"] = magics
    return magics

def _spell(spell_id):
    for spell in get_game_config().get("magics", []):
        if int(spell["id"]) == int(spell_id):
            return spell
    return None

def _item_attrs(item: list) -> dict:
    "The attributes dict of a map item (index 7), created if missing. The client reads it as loaded.attrs."
    while len(item) < 6:
        item.append(0)
    if len(item) < 7 or not isinstance(item[6], list):
        if len(item) < 7:
            item.append([])
        else:
            item[6] = []
    if len(item) < 8 or not isinstance(item[7], dict):
        if len(item) < 8:
            item.append({})
        else:
            item[7] = {}
    return item[7]

def _find_building(map: dict, x, y, item_id):
    item = find_map_item(map, x, y, item_id)
    if item is None:
        item = find_map_item(map, x, y)
    return item

def _social_item(item_id):
    for si in get_game_config().get("social_items", []):
        if int(si["id"]) == int(item_id):
            return si
    return None

# --- market (popups/ButtonMarket.as, core/Base.as processAttacks) -------------

MARKET_BASE_COSTS = {"f": 100, "s": 150, "w": 100}   # Config.as
MARKET_MAX_NUM_TRADES = 20
MARKET_INCREMENT = 0.02
MARKET_MAX_INCREMENTS = 200
MARKET_MAX_DECREMENTS = 25
MARKET_SELL_PERCENTAGE = 0.75
MARKET_PERIOD_HOURS = 20

def trade_resource(save, args):
    # args: [townID, resource 'f'/'w'/'s', sell 1/0, amount]
    map = town(save, args[0])
    resource = str(args[1])
    sell = _bool(args[2])
    amount = _int(args[3])
    if resource not in MARKET_BASE_COSTS or amount <= 0:
        print(f"Invalid trade ignored: {args}")
        return
    traded = map.get("resourcesTraded")
    if not isinstance(traded, dict):
        traded = {}
        map["resourcesTraded"] = traded
    n_traded = _int(traded.get(resource, 0))
    # Same price formula as ButtonMarket.refreshCost()
    base = MARKET_BASE_COSTS[resource] * (amount / 100)
    cost = _as_round(base + base * n_traded * MARKET_INCREMENT)
    if sell:
        cost = _as_round(cost * MARKET_SELL_PERCENTAGE)
        add_resource(save, map, "g", cost)
        spend(save, map, resource, amount)
    else:
        spend(save, map, "g", cost)
        add_resource(save, map, resource, amount)
    # Buying makes the resource more expensive, selling cheaper.
    n_traded = n_traded + (-1 if sell else 1)
    traded[resource] = min(max(-MARKET_MAX_DECREMENTS, n_traded), MARKET_MAX_INCREMENTS)
    # Trades counter: the client resets it at login when the period started more than 20h ago.
    now = timestamp_now()
    if now - _int(map.get("timestampLastTrade", 0)) > 3600 * MARKET_PERIOD_HOURS:
        map["numTradesDone"] = 0
        map["timestampLastTrade"] = now
    map["numTradesDone"] = _int(map.get("numTradesDone", 0)) + 1
    print(f"{'Sell' if sell else 'Buy'} {amount} {resource} for {cost} gold. Trades done: {map['numTradesDone']}/{MARKET_MAX_NUM_TRADES}")

ALLIES_MARKETS = (266, 352)            # ID_BUILDING_MARKET_ALLIES, ID_BUILDING_TROLL_MARKET_ALLIES
RESOURCES_MARKET_PER_ALLY = 125         # Config.as

def set_resource_allies(save, args):
    # args: [resource ('n' = none), x, y, townID, building id]
    resource = str(args[0])
    map = town(save, args[3])
    map["resourceAlliesMarket"] = resource
    if resource != "n":
        # PopupSelectResource: the 24h production timer starts now (activation 86400, collected_at 0).
        item = _find_building(map, args[1], args[2], args[4])
        if item is not None:
            item[4] = timestamp_now()
    print(f"Allies market resource set to '{resource}'")

# --- social buildings: "si" = social item helpers (attrs.si of the building) ----

# Buildings that keep asking for helpers again and again (IsoInteractiveElement.as): after
# finish_si the client empties attrs.si. Any other social building is complete: attrs.si = null.
REUSABLE_SOCIAL_BUILDINGS = (234, 266, 352, 387, 389, 470)  # summit, allies markets, recruitment, round table, wonder

def buy_si_help(save, args):
    # args: [x, y, townID, building id] (cash: worker_cost) or [..., 1] (free, sent by the game itself)
    x, y, item_id = args[0], args[1], _int(args[3])
    map = town(save, args[2])
    free = len(args) > 4 and _int(args[4]) == 1
    item = _find_building(map, x, y, item_id)
    social = _social_item(item_id)
    price = _int(social["worker_cost"]) if social and not free else 0
    if price > 0:
        spend_cash(save, price)
    if item is None:
        print(f"Bought helper for {item_name(item_id)} ({price} cash), building not found at ({x},{y})")
        return
    attrs = _item_attrs(item)
    si = attrs.get("si")
    if not isinstance(si, list):
        si = []
        attrs["si"] = si
    n_workers = len(str(social["workers"]).split(",")) if social else None
    if n_workers is None or len(si) < max(n_workers, 20):
        si.append(0)
    print(f"Helper bought for {item_name(item_id)} at ({x},{y}) ({price} cash). Helpers: {len(si)}")

def finish_si(save, args):
    # args: [x, y, townID, building id] (+ [gold, xp, item_id] from the Round Table, PopupSocialFeeds.as)
    x, y, item_id = args[0], args[1], _int(args[3])
    map = town(save, args[2])
    item = _find_building(map, x, y, item_id)
    attrs = _item_attrs(item) if item is not None else {}
    si = attrs.get("si")
    n_helpers = len(si) if isinstance(si, list) else 0
    extra = ""
    if item_id in ALLIES_MARKETS:
        # IsoElement.collect: the allies market gives 125 * (helpers + 1) of the chosen resource.
        resource = map.get("resourceAlliesMarket")
        ready = item is not None and timestamp_now() - _int(item[4]) >= _int(item_attr(item_id, "activation", 86400)) - 60
        if resource in ("g", "w", "s", "f") and ready:
            amount = RESOURCES_MARKET_PER_ALLY * (n_helpers + 1)
            add_resource(save, map, resource, amount)
            extra = f", +{amount} {resource}"
    if len(args) >= 7:
        gold, xp, reward = _int(args[4]), _int(args[5]), _int(args[6])
        add_resource(save, map, "g", gold)
        _add(save, map, "x", xp)
        if reward > 0:
            _store_add(map, reward)
        attrs["sif"] = []
        extra = f", +{gold} gold, +{xp} xp" + (f", {item_name(reward)} to inventory" if reward > 0 else "")
    if item is not None:
        if item_id in REUSABLE_SOCIAL_BUILDINGS:
            attrs["si"] = []
        else:
            attrs.pop("si", None)  # construction finished
    print(f"Social building {item_name(item_id)} finished with {n_helpers} helpers{extra}")

def finish_dragon_help(save, args):
    # PopupDragons.closeHireResults: the friends who helped were counted (next_dragon_step sent for each step).
    friends = json_arg(args[0]) if args else []
    save["privateState"]["dragonSocialHelp"] = []
    print(f"Dragon nest friends help cleared ({len(friends) if isinstance(friends, list) else 0} friends)")

# --- magic (GUI/SelectedMagic.as, core/MagicManager.as, popups/PopupBuyMana.as) ---

def buy_magic(save, args):
    # args: [spell id, townID, 0 = gold / 1 = cash]
    spell = _spell(args[0])
    if spell is None:
        print(f"Unknown spell {args[0]}, ignored")
        return
    map = town(save, args[1])
    with_cash = _int(args[2]) == 1
    if with_cash:
        spend_cash(save, _int(spell["cash"]))
    else:
        spend(save, map, "g", _int(spell["gold"]))
    magics = _magics(save)
    key = str(spell["id"])
    if key not in magics:
        magics[key] = 0
    _add_mana(save, _int(spell["mana"]))  # updateMagicEntry: learning a spell gives its mana cost
    print(f"Learned spell {spell['name']} for {spell['cash'] if with_cash else spell['gold']} {'cash' if with_cash else 'gold'}")

def use_magic(save, args):
    # args: [spell id]
    spell = _spell(args[0])
    if spell is None:
        print(f"Unknown spell {args[0]}, ignored")
        return
    _add_mana(save, -_int(spell["mana"]))
    magics = _magics(save)
    key = str(spell["id"])
    magics[key] = _int(magics.get(key, 0)) + 1  # MagicSpell.castSpell: uses count -> spell level
    print(f"Cast {spell['name']} (-{spell['mana']} mana, {magics[key]} uses)")

def buy_mana(save, args):
    # args: [townID, 0 = gold / 1 = cash]
    g = _globals()
    map = town(save, args[0])
    with_cash = len(args) > 1 and _int(args[1]) == 1
    if with_cash:
        price = _int(g.get("COST_MANA_CASH", 1))
        spend_cash(save, price)
    else:
        price = _int(g.get("COST_MANA_GOLD", 20000))
        spend(save, map, "g", price)
    mana = _int(g.get("MANA_PER_PURCHASE", 5))
    _add_mana(save, mana)
    print(f"Bought {mana} mana for {price} {'cash' if with_cash else 'gold'}")

# --- darts (popups/PopupDarts.as) ---------------------------------------------
# The prizes are sent separately with store_add_items: not granted here.

NUM_BALLOONS = 25  # PopupDarts.NUM_BALLOONS

def darts_reset(save, args):
    now = timestamp_now()
    ps = save["privateState"]
    ps["timeStampDartsReset"] = now
    ps["timeStampDartsNewFree"] = now
    ps["dartsBalloonsShot"] = []
    ps["dartsRandomSeed"] = _int(args[0]) if args else 0
    ps["dartsHasFree"] = True
    ps["dartsGotExtra"] = False
    print("Darts game reset, seed", ps["dartsRandomSeed"])

def darts_new_free(save, args):
    ps = save["privateState"]
    ps["timeStampDartsNewFree"] = timestamp_now()
    ps["dartsHasFree"] = True
    print("New free dart")

def darts_shoot_balloon(save, args):
    # args: [balloon index, 0 = free dart / 1 = paid dart, 1 = got the extra prize]
    balloon = _int(args[0], -1)
    paid = len(args) > 1 and _int(args[1]) == 1
    got_extra = len(args) > 2 and _int(args[2]) == 1
    ps = save["privateState"]
    shot = private(save, "dartsBalloonsShot", [])
    if not isinstance(shot, list):
        shot = []
        ps["dartsBalloonsShot"] = shot
    if 0 <= balloon < NUM_BALLOONS and balloon not in shot:
        shot.append(balloon)
    price = 0
    if paid:
        # The client takes the cash when "play" is clicked, without a command of its own.
        price = _int(_globals().get("DART_COST_CASH", 20))
        spend_cash(save, price)
    ps["dartsHasFree"] = False
    if got_extra:
        ps["dartsGotExtra"] = True
    print(f"Dart hit balloon {balloon}" + (f" ({price} cash)" if paid else " (free dart)") + (", extra prize won" if got_extra else ""))

# --- offer packs (core/PromotionPacks.as buyPack) ------------------------------

def buy_offer_pack(save, args):
    # args: [townID, pack number (offer_packs[number - 1])] or [..., won item id] for random packs
    map = town(save, args[0])
    number = _int(args[1])
    packs = get_game_config().get("offer_packs", [])
    if not 1 <= number <= len(packs):
        print(f"Unknown offer pack {number}, ignored")
        return
    pack = packs[number - 1]
    spend_cash(save, _int(pack.get("cost_cash", 0)))
    _add(save, map, "g", _int(pack.get("gold", 0)))
    _add(save, map, "x", _int(pack.get("xp", 0)))
    _add(save, map, "s", _int(pack.get("stone", 0)))
    _add(save, map, "f", _int(pack.get("food", 0)))
    _add(save, map, "w", _int(pack.get("wood", 0)))
    _add(save, map, "m", _int(pack.get("mana", 0)))
    # The client puts the items in the inventory without sending store commands.
    items = []
    if _int(pack.get("pack_type", 0)) == 1:
        if len(args) > 2:
            items = [_int(args[2])]
    elif isinstance(pack.get("items"), list):
        items = [_int(i) for i in pack["items"] if not isinstance(i, list)]
    for item_id in items:
        if item_id > 0:
            _store_add(map, item_id)
    print(f"Offer pack {number} bought for {pack.get('cost_cash', 0)} cash. Items: {', '.join(item_name(i) for i in items) or 'none'}")

# --- Bahamut Supreme Invocation Temple (popups/PopupBahamutSupremeInvocationTemple.as) ---
# privateState.templeStep = list of the steps done, privateState.timeStampTemple = when the last step
# was done (48h wait before the next one, 0 = no wait).

ID_BUILDING_BAHAMUT_SUPREME_INVOCATION_TEMPLE = 1394

def _temple_map(save: dict) -> dict:
    "No town id in the temple commands: use the island that has the temple."
    for map in save["maps"]:
        if any(item[0] == ID_BUILDING_BAHAMUT_SUPREME_INVOCATION_TEMPLE for item in map.get("items", [])):
            return map
    return save["maps"][0]

def _temple_steps(save: dict) -> list:
    steps = private(save, "templeStep", [])
    if not isinstance(steps, list):
        steps = []
        save["privateState"]["templeStep"] = steps
    return steps

def next_temple_step(save, args):
    # args: [JSON data, step index]. data = {"g": 100000} (resources paid), {"u": unit id} (sacrifice,
    # the unit removal is a separate sell command) or {"collection": 23}.
    data = json_arg(args[0])
    step = _int(args[1], -1)
    if not 0 <= step < 12:
        print(f"Invalid temple step {args[1]}, ignored")
        return
    steps = _temple_steps(save)
    if step in steps:
        print(f"Temple step {step} already done")
        return
    paid = ""
    if isinstance(data, dict) and not ("u" in data or "collection" in data):
        map = _temple_map(save)
        for cost_type, amount in data.items():
            if cost_type in ("g", "w", "s", "f", "c", "m"):
                _add(save, map, cost_type, -_int(amount))
        paid = " paying " + ", ".join(f"{v} {k}" for k, v in data.items())
    steps.append(step)
    save["privateState"]["timeStampTemple"] = timestamp_now()
    print(f"Temple step {step} done{paid}. Steps: {len(steps)}/12")

def buy_temple_step_cash(save, args):
    # args: [cash price] -> skips the wait
    price = _int(args[0]) if args else 5
    spend_cash(save, price)
    save["privateState"]["timeStampTemple"] = 0
    print(f"Temple wait skipped for {price} cash")

def reset_temple(save, args):
    save["privateState"]["templeStep"] = []
    save["privateState"]["timeStampTemple"] = 0
    print("Temple progress reset")

# --- flags and misc -------------------------------------------------------------

def set_info_showed(save, args):
    # args: [key, bool]. The client reads privateState.infoShowed as an object {key: bool}.
    key = str(args[0])
    value = _bool(args[1]) if len(args) > 1 else True
    info = save["privateState"].get("infoShowed")
    if not isinstance(info, dict):
        info = {}
        save["privateState"]["infoShowed"] = info
    info[key] = value
    print(f"Info '{key}' showed: {value}")

def set_quest_var(save, args):
    # args: [townID, key, JSON value]. Read back at login as map.currentQuestVars (Base.currentQuestProperties).
    map = town(save, args[0])
    key = str(args[1])
    value = json_arg(args[2]) if len(args) > 2 else None
    qv = map.get("currentQuestVars")
    if not isinstance(qv, dict):
        qv = {}
        map["currentQuestVars"] = qv
    qv[key] = value
    print(f"Quest var '{key}' = {value}")

def set_variables(save, args):
    # Admin panel: args [gold, cash, xp, level, stone, wood, food, townID] (absolute values)
    map = town(save, args[7]) if len(args) > 7 else save["maps"][0]
    gold, cash, xp, level, stone, wood, food = (max(_int(a), 0) for a in args[:7])
    map["coins"] = gold
    map["stone"] = stone
    map["wood"] = wood
    map["food"] = food
    save["playerInfo"]["cash"] = cash
    map0 = _map0(save)
    map0["xp"] = xp
    map0["level"] = max(level, 1)
    print(f"Admin set variables: gold {gold}, cash {cash}, xp {xp}, level {level}, stone {stone}, wood {wood}, food {food}")

def clear_message(save, args):
    # The server message (privateState.message) was shown once.
    save["privateState"].pop("message", None)
    print("Server message cleared")

def perform_city_quest(save, args):
    # args: [x, y, townID, quest id]. The building's collect timer restarts (collected_at = 0).
    map = town(save, args[2])
    item = find_map_item(map, args[0], args[1])
    if item is not None:
        item[4] = timestamp_now()
    print(f"City quest {args[3] if len(args) > 3 else ''} performed at ({args[0]},{args[1]})")

HANDLERS = {
    "trade_resource_b": trade_resource,
    "set_resource_allies": set_resource_allies,
    "buy_si_help": buy_si_help,
    "finish_si": finish_si,
    "finish_dragon_help": finish_dragon_help,
    "buy_magic": buy_magic,
    "use_magic": use_magic,
    "buy_mana_new": buy_mana,
    "darts_reset": darts_reset,
    "darts_new_free": darts_new_free,
    "darts_shoot_balloon": darts_shoot_balloon,
    "buy_offer_pack": buy_offer_pack,
    "next_temple_step": next_temple_step,
    "buy_temple_step_cash": buy_temple_step_cash,
    "reset_temple": reset_temple,
    "set_info_showed": set_info_showed,
    "set_quest_var": set_quest_var,
    "set_variables": set_variables,
    "clear_message": clear_message,
    "perform_city_quest": perform_city_quest,
}
