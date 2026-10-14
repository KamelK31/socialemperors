"""Battle / PvP / survival / assists commands.

In this private server the "other players" are the static neighbour villages (villages/*.json)
or other local saves. Only the local player's side is stored here: the victim of an attack, the
neighbour that was assisted, etc. are never modified.
"""
import json

from cmd_helpers import town, item_attr, item_name, add_resource, spend, spend_cash, find_map_item, \
    _store_add, json_arg, private
from engine import timestamp_now
from get_game_config import get_game_config

# Client constants (core/Config.as)
ATTACKS_PACK_SIZE = 50          # Config.ATTACKS_PACK_SIZE
SPYINGS_PACK_SIZE = 50          # Config.SPYINGS_PACK_SIZE
COST_BUY_ATTACK = 30            # Config.COST_BUY_ATTACK (cash)
COST_BUY_SPYINGS = 15           # Config.COST_BUY_SPYINGS (cash)
ASSIST_CLICK_REWARD_GOLD = 10   # Config.ASSIST_CLICK_REWARD_GOLD
ASSIST_CLICK_REWARD_XP = 3      # Config.ASSIST_CLICK_REWARD_XP
NUM_CLICKS_ASSIST = 5           # NeighbourManager.NUM_CLICKS_ASSIST
FRIENDS_ASSIST_DIVISOR = 0.25   # Config.FRIENDS_ASSIST_DIVISOR
FRIENDS_ASSIST_EXPERIENCE = 10  # Config.FRIENDS_ASSIST_EXPERIENCE
SURVIVAL_MAX_LIVES = 3          # PopupSurvival: 3 regular lives
UNIVERSE_ISLAND_SIZE = 7        # ExplorationsManager: 7 villages to conquer per island
HISTORY_MAX = 100               # attacksSent / spyings entries kept (the client only needs the last hours)

def _globals() -> dict:
    return get_game_config()["globals"]

def _global_int(key: str, default: int) -> int:
    try:
        return int(_globals()[key])
    except (KeyError, ValueError, TypeError):
        return default

def _int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def _home(save: dict) -> dict:
    "The map the client reads as Base.Player.mapInfo (get_player_info always sends maps[0])."
    return save["maps"][0]

def _list(container: dict, key: str) -> list:
    value = container.get(key)
    if not isinstance(value, list):
        value = []
        container[key] = value
    return value

def _dict(container: dict, key: str) -> dict:
    value = container.get(key)
    if not isinstance(value, dict):
        value = {}
        container[key] = value
    return value

def _trim(history: list) -> None:
    if len(history) > HISTORY_MAX:
        del history[:len(history) - HISTORY_MAX]

def _counted_items(value) -> dict:
    "Rewards sent as a JSON object {item_id: count} (or null)."
    items = json_arg(value)
    if not isinstance(items, dict):
        return {}
    out = {}
    for item_id, count in items.items():
        item_id, count = _int(item_id, -1), _int(count)
        if item_id > 0 and count > 0:
            out[item_id] = out.get(item_id, 0) + count
    return out

def _attack_counters(save: dict) -> None:
    "Keys read by Base.processAttacks at login. A missing tsAttacksReset makes the client ignore every attack sent."
    private(save, "attacksSent", [])
    private(save, "attacksReceived", [])
    private(save, "tsAttacksReset", 0)
    private(save, "attacksPack", 0)

def _spy_counters(save: dict) -> None:
    private(save, "spyings", [])
    private(save, "tsSpyingsReset", 0)
    private(save, "spyingsPack", 0)

def _remove_units(map: dict, unit_id: int, count: int) -> int:
    "Removes `count` units with this id standing on the map (the attacking army). Returns how many were removed."
    removed = 0
    for item in list(map["items"]):
        if removed >= count:
            break
        if isinstance(item, list) and len(item) >= 3 and item[0] == unit_id:
            map["items"].remove(item)
            removed += 1
    return removed

def _conquer(save: dict, position) -> None:
    "Adds a village of the PvP island to map.universAttackWin. With the 7 conquered the client moves to the next island."
    home = _home(save)
    conquered = _list(home, "universAttackWin")
    position = _int(position, -1)
    if position < 0 or position in conquered:
        return
    conquered.append(position)
    if len(conquered) >= UNIVERSE_ISLAND_SIZE:
        # Client (ExplorationsManager.checkAnimationConquered / setProgress): worldChange = 1, conquered list emptied.
        save["privateState"]["worldChange"] = 1
        home["universAttackWin"] = []

# --- PvP attacks -------------------------------------------------------------

def attack_player(save, args):
    # args: [victim user_id]. The client decrements Base.Main.numAttacks.
    victim_id = str(args[0]) if args else ""
    _attack_counters(save)
    ps = save["privateState"]
    if _int(ps.get("attacksPack")) > 0:
        ps["attacksPack"] = _int(ps["attacksPack"]) - 1
    attacks = _list(ps, "attacksSent")
    attacks.append({"victim_id": victim_id, "time": timestamp_now()})
    _trim(attacks)
    print("Attack player", victim_id, "| attacks pack left:", ps["attacksPack"])

def end_attack(save, args):
    # args: [JSON result, (optional) enemy had no town hall]. Sent by Assault.sendAssaultResults.
    data = json_arg(args[0])
    if not isinstance(data, dict):
        raise ValueError("end_attack: bad result")
    attacker = data.get("attacker") if isinstance(data.get("attacker"), dict) else {}
    victim = data.get("victim") if isinstance(data.get("victim"), dict) else {}
    resources = data.get("resources") if isinstance(data.get("resources"), dict) else {}
    gold = max(_int(resources.get("g")), 0)
    xp = max(_int(resources.get("x")), 0)
    win = _int(data.get("win")) == 1
    honor = max(_int(data.get("honor")), 0)
    map = town(save, attacker.get("map", 0))
    _attack_counters(save)
    ps = save["privateState"]

    # Loot: in assault mode the client shows the tokens but only the server adds them (reloaded on return home).
    add_resource(save, map, "g", gold)
    add_resource(save, map, "x", xp)
    if honor:
        ps["honor"] = _int(ps.get("honor")) + honor

    # Units lost: [unit_id, init, killed, recovered]; killed - recovered never come back.
    # (Attacking units are spawned with inServer = false, so the client sends no sell/kill command for them.)
    lost = []
    units = data.get("attacker_units")
    for entry in units if isinstance(units, list) else []:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        unit_id = _int(entry[0], -1)
        n = _int(entry[2]) - (_int(entry[3]) if len(entry) > 3 else 0)
        if unit_id > 0 and n > 0:
            removed = _remove_units(map, unit_id, n)
            if removed:
                lost.append(f"{removed} {item_name(unit_id)}")

    # History (PopupAssaultHistory reads time and description.oponent/resources/win/units)
    description = {
        "oponent": victim,
        "resources": {"g": gold, "x": xp},
        "resources_victim": data.get("resources_victim", {"g": 0}),
        "attacker_units": data.get("attacker_units", []),
        "victim_units": data.get("victim_units", []),
        "win": 1 if win else 0,
        "duration": data.get("duration", 0),
        "voluntary_end": data.get("voluntary_end", 0),
        "townhall_gold": data.get("townhall_gold", 0),
        "honor": honor,
    }
    victim_id = str(victim.get("user_id", ""))
    attacks = _list(ps, "attacksSent")
    record = None
    for attack in reversed(attacks):
        if isinstance(attack, dict) and "description" not in attack and str(attack.get("victim_id")) == victim_id:
            record = attack
            break
    if record is None: # attack_player was not received: count the attack here
        record = {"victim_id": victim_id, "time": timestamp_now()}
        attacks.append(record)
        _trim(attacks)
    record["description"] = description

    # PvP island progress
    if win and "posicion" in victim:
        _conquer(save, victim["posicion"])

    print("Attack on", victim.get("name", victim_id), "won" if win else "lost", f"| +{gold} gold, +{xp} xp, +{honor} honor.",
          "Units lost:", ", ".join(lost) if lost else "none")

def set_attack_team(save, args):
    # args: [team name ("tournament", "quest"...), JSON list of unit ids]
    name = str(args[0])
    team = json_arg(args[1]) if len(args) > 1 else []
    if not isinstance(team, list):
        raise ValueError("set_attack_team: bad team")
    teams = _dict(save["privateState"], "teams")
    teams[name] = [_int(u) for u in team]
    print("Team", name, "set to", teams[name])

def buy_attacks_pack(save, args):
    # Client: -COST_BUY_ATTACK cash, numAttacks = ATTACKS_PACK_SIZE
    _attack_counters(save)
    ps = save["privateState"]
    spend_cash(save, COST_BUY_ATTACK)
    ps["attacksPack"] = ATTACKS_PACK_SIZE
    ps["tsAttacksReset"] = timestamp_now()
    print(f"Bought {ATTACKS_PACK_SIZE} attacks for {COST_BUY_ATTACK} cash")

def buy_spyings_pack(save, args):
    # Client: -COST_BUY_SPYINGS cash, numSpyings = SPYINGS_PACK_SIZE
    _spy_counters(save)
    ps = save["privateState"]
    spend_cash(save, COST_BUY_SPYINGS)
    ps["spyingsPack"] = SPYINGS_PACK_SIZE
    ps["tsSpyingsReset"] = timestamp_now()
    print(f"Bought {SPYINGS_PACK_SIZE} spyings for {COST_BUY_SPYINGS} cash")

def spy_player(save, args):
    # args: [victim user_id]. Counted at login from privateState.spyings (time of each spying).
    victim_id = str(args[0]) if args else ""
    _spy_counters(save)
    ps = save["privateState"]
    if _int(ps.get("spyingsPack")) > 0:
        ps["spyingsPack"] = _int(ps["spyingsPack"]) - 1
    spyings = _list(ps, "spyings")
    spyings.append({"victim_id": victim_id, "time": timestamp_now()})
    _trim(spyings)
    print("Spy player", victim_id, "| spyings pack left:", ps["spyingsPack"])

def buy_pvp_territory(save, args):
    # args: [position on the island]. Client: -PVP_BUY_TERRITORY_CASH cash, position pushed to universAttackWin.
    position = _int(args[0], -1) if args else -1
    if position < 0:
        raise ValueError("buy_pvp_territory: bad position")
    cost = _global_int("PVP_BUY_TERRITORY_CASH", 5)
    spend_cash(save, cost)
    _conquer(save, position)
    print(f"Bought PvP territory {position} for {cost} cash")

def clean_attacks(save, args):
    # Sent after the history popup showed the new attacks received: they are no longer "new".
    received = private(save, "attacksReceived", [])
    n = 0
    for attack in received if isinstance(received, list) else []:
        if isinstance(attack, dict) and attack.pop("viewPending", None) is not None:
            n += 1
    print("Attacks received marked as seen:", n)

# --- PvP island (universe) ---------------------------------------------------

def modify_position_univers(save, args):
    # args: [old position, new position] of the player on the island. The island layout comes from
    # get_continent_ranking.php (a stub in this server), the save stores nothing about it.
    print("Island position", args[0] if args else "?", "->", args[1] if len(args) > 1 else "?", "(not stored: island layout is generated by the server)")

def reset_position_univers(save, args):
    # "Relocate": the client empties universAttackWin.
    _home(save)["universAttackWin"] = []
    print("PvP island progress reset")

def reset_world_change(save, args):
    # The client showed the "next island" popup and set privateState.worldChange = 0.
    save["privateState"]["worldChange"] = 0
    print("Island change acknowledged")

def apply_rewards_ranking(save, args):
    # args: [island level, cash, JSON {item_id: count}]. PopupNextIslandAttack.givePrizes: +cash, items stored.
    level = args[0] if args else "?"
    cash = max(_int(args[1]), 0) if len(args) > 1 else 0
    items = _counted_items(args[2]) if len(args) > 2 else {}
    map = _home(save)
    add_resource(save, map, "c", cash)
    for item_id, count in items.items():
        _store_add(map, item_id, count)
    print(f"Island {level} rewards: +{cash} cash" + "".join(f", {c} {item_name(i)}" for i, c in items.items()))

# --- Heavy siege -------------------------------------------------------------

def start_heavy_siege(save, args):
    save["privateState"]["timeStampHeavySiegeAttack"] = timestamp_now()
    print("Heavy siege started")

def reset_heavy_siege(save, args):
    # args: [1 if paid with cash, reward item id (0 = none)]. MapInitializer.resetHeavySiege / PopupHeavySiege.
    paid = _int(args[0]) == 1 if args else False
    reward = _int(args[1]) if len(args) > 1 else 0
    ps = save["privateState"]
    ps["timeStampHeavySiegeAttack"] = 0
    ps["timeStampHeavySiegePeriod"] = timestamp_now()
    if paid:
        spend_cash(save, _global_int("HEAVY_SIEGE_COST_CASH", 20))
    if reward > 0:
        _store_add(_home(save), reward)
    print("Heavy siege ended." + (" Paid with cash." if paid else "") + (f" Reward: {item_name(reward)}" if reward > 0 else ""))

# --- Survival ----------------------------------------------------------------

def start_survival(save, args):
    # Uses one life: a regular one (survivalVidaTimeStamp, each regenerates after SURVIVAL_HOURS_LIVE_REGENERATE), else an extra one.
    ps = save["privateState"]
    now = timestamp_now()
    regen = _global_int("SURVIVAL_HOURS_LIVE_REGENERATE", 3) * 3600
    used = [ts for ts in _list(ps, "survivalVidaTimeStamp") if _int(ts) + regen > now]
    if len(used) < SURVIVAL_MAX_LIVES:
        used.append(now)
        how = "regular life"
    elif _int(ps.get("survivalVidasExtra")) > 0:
        ps["survivalVidasExtra"] = _int(ps["survivalVidasExtra"]) - 1
        how = "extra life"
    else:
        how = "no life left"
    ps["survivalVidaTimeStamp"] = used
    print("Survival started:", how)

def end_survival(save, args):
    # args: [map id, seconds survived, JSON {item_id: count} or null]. PopupSurvivalResults.givePrizes stores the items.
    map_id = str(args[0]) if args else ""
    seconds = max(_int(args[1]), 0) if len(args) > 1 else 0
    items = _counted_items(args[2]) if len(args) > 2 else {}
    maps = _dict(save["privateState"], "survivalMaps")
    record = maps.get(map_id)
    if not isinstance(record, dict):
        record = {"ts": 0, "tp": 0}
        maps[map_id] = record
    record["ts"] = timestamp_now()
    record["tp"] = max(_int(record.get("tp")), seconds) # shown as "best time"
    home = _home(save)
    for item_id, count in items.items():
        _store_add(home, item_id, count)
    print(f"Survival {map_id} ended after {seconds}s.", "Rewards: " + ", ".join(f"{c} {item_name(i)}" for i, c in items.items()) if items else "No reward.")

def buy_survival_map(save, args):
    # args: [map id, cash price]
    map_id = str(args[0])
    cost = max(_int(args[1]), 0) if len(args) > 1 else 0
    spend_cash(save, cost)
    maps = _dict(save["privateState"], "survivalMaps")
    if not isinstance(maps.get(map_id), dict):
        maps[map_id] = {"ts": 0, "tp": 0}
    print(f"Survival map {map_id} unlocked for {cost} cash")

def add_survival_vida_extra(save, args):
    # args: [cash price]
    cost = max(_int(args[0]), 0) if args else _global_int("SURVIVAL_BUY_LIVE_CASH", 3)
    spend_cash(save, cost)
    ps = save["privateState"]
    ps["survivalVidasExtra"] = _int(ps.get("survivalVidasExtra")) + 1
    print(f"Bought a survival life for {cost} cash ({ps['survivalVidasExtra']} extra)")

# --- Tournament --------------------------------------------------------------

def tournament_substract_resources(save, args):
    # args: [cost type "g"/"c", amount, tournament type, flag]
    cost_type = str(args[0])
    amount = max(_int(args[1]), 0)
    if cost_type not in ("g", "c"):
        raise ValueError("tournament_substract_resources: bad cost type")
    spend(save, _home(save), cost_type, amount)
    print(f"Tournament {args[2] if len(args) > 2 else '?'} entry: -{amount} {'gold' if cost_type == 'g' else 'cash'}")

def tournament_refund_resources(save, args):
    # args: [cost type "g"/"c", amount]
    cost_type = str(args[0])
    amount = max(_int(args[1]), 0)
    if cost_type not in ("g", "c"):
        raise ValueError("tournament_refund_resources: bad cost type")
    add_resource(save, _home(save), cost_type, amount)
    print(f"Tournament refund: +{amount} {'gold' if cost_type == 'g' else 'cash'}")

# --- Assists -----------------------------------------------------------------

def _mark_assisted(save, friend_id) -> None:
    # Base.as login: an assist is available again 24h after privateState.neighborAssists["u" + pid]
    _dict(save["privateState"], "neighborAssists")["u" + str(friend_id)] = timestamp_now()

def assist_neighbor(save, args):
    # args: [friend pid, assist id, town id]. FauxBar2: +ASSIST_REWARD_GOLD gold, +ASSIST_REWARD_XP xp to the player.
    friend_id = str(args[0])
    gold = _global_int("ASSIST_REWARD_GOLD", 10)
    xp = _global_int("ASSIST_REWARD_XP", 3)
    map = _home(save)
    add_resource(save, map, "g", gold)
    add_resource(save, map, "x", xp)
    _mark_assisted(save, friend_id)
    print(f"Assisted neighbour {friend_id}: +{gold} gold, +{xp} xp")

def assist_neighbor_new(save, args):
    # args: [friend pid, 0, JSON [[x, y, building id], ...]] (buildings clicked while visiting).
    # Each click showed +ASSIST_CLICK_REWARD_GOLD gold / +ASSIST_CLICK_REWARD_XP xp, which only the server adds.
    friend_id = str(args[0])
    clicks = json_arg(args[2]) if len(args) > 2 else []
    n = min(len(clicks), NUM_CLICKS_ASSIST) if isinstance(clicks, list) else 0
    map = _home(save)
    add_resource(save, map, "g", n * ASSIST_CLICK_REWARD_GOLD)
    add_resource(save, map, "x", n * ASSIST_CLICK_REWARD_XP)
    _mark_assisted(save, friend_id)
    print(f"Assisted {n} buildings of neighbour {friend_id}: +{n * ASSIST_CLICK_REWARD_GOLD} gold, +{n * ASSIST_CLICK_REWARD_XP} xp")

def assist_receive(save, args):
    # args: [town id, building id]. IACartAlly: a friend's cart gives collect/4 of the building's resource and 10 xp.
    map = town(save, args[0])
    building_id = _int(args[1])
    collect_type = item_attr(building_id, "collect_type", "")
    amount = int(float(item_attr(building_id, "collect", 0) or 0) * FRIENDS_ASSIST_DIVISOR)
    if collect_type in ("g", "w", "s", "f") and amount > 0:
        add_resource(save, map, collect_type, amount)
    add_resource(save, map, "x", FRIENDS_ASSIST_EXPERIENCE)
    print(f"Assist received on {item_name(building_id)}: +{amount} {collect_type}, +{FRIENDS_ASSIST_EXPERIENCE} xp")

def clean_received_assists(save, args):
    # args: [friend id, town id]. The assist of this friend was accepted or refused: remove it from map.receivedAssists.
    friend_id = str(args[0])
    map = town(save, args[1] if len(args) > 1 else 0)
    received = _dict(map, "receivedAssists")
    removed = received.pop("u" + friend_id, None) is not None
    removed = received.pop(friend_id, None) is not None or removed
    print("Received assist of", friend_id, "removed" if removed else "(none stored)")

def _item_attrs(item: list) -> dict:
    "item[7] = attrs dict (item[6] = units inside)."
    while len(item) < 6:
        item.append(0)
    if len(item) < 7:
        item.append([])
    if len(item) < 8 or not isinstance(item[7], dict):
        item[7:8] = [{}]
    return item[7]

def assist_send_feed(save, args):
    # args: [x, y, town id, building id, friend id]. PopupSocialFeeds: attrs.sif[friend] = true (request sent).
    x, y, building_id, friend_id = args[0], args[1], _int(args[3]), str(args[4])
    map = town(save, args[2])
    item = find_map_item(map, x, y, building_id)
    if item is not None:
        _dict(_item_attrs(item), "sif")[friend_id] = True
    print(f"Help request for {item_name(building_id)} sent to {friend_id}" + ("" if item else " (building not found)"))

def accept_collect_help(save, args):
    # args: [x, y, town id, building id, friend id]. IsoElement.collectHurryUp: collected_at += COLLECT_HELP_SECONDS
    # (the client's collected_at is the time elapsed since item[4]), attrs.hc[friend] = true.
    x, y, building_id, friend_id = args[0], args[1], _int(args[3]), str(args[4])
    map = town(save, args[2])
    item = find_map_item(map, x, y, building_id)
    if item is None:
        print("Collect help: building", item_name(building_id), "not found at", (x, y))
        return
    seconds = _global_int("COLLECT_HELP_SECONDS", 3600)
    item[4] = _int(item[4]) - seconds
    helped = _dict(_item_attrs(item), "hc")
    key = "u" + friend_id if ("u" + friend_id) in helped else friend_id
    helped[key] = True
    print(f"Collect help of {friend_id} accepted on {item_name(building_id)}: -{seconds}s")

def set_help_map(save, args):
    # args: [help popup type] seen by the player (privateState.helpMap)
    help_type = str(args[0])
    seen = private(save, "helpMap", [])
    if not isinstance(seen, list):
        seen = save["privateState"]["helpMap"] = []
    if help_type not in seen:
        seen.append(help_type)
    print("Help seen:", help_type)

def set_fake_neighbors(save, args):
    # args: up to 3 friend ids ("0" = none). The client stores them in privateState.fakeNeighbors (FriendsWindow).
    fakes = [str(a) for a in args if str(a) not in ("0", "")]
    save["privateState"]["fakeNeighbors"] = fakes
    print("Fake neighbours:", fakes)

# --- Misc --------------------------------------------------------------------

def cross_promotion_finished(save, args):
    # args: [game id]. CrossManager.getCrossPromotionUnit: id pushed to privateState.crossPromotionsFinished.
    # The reward unit comes from the external cross-promotion service (not in args, never active here).
    game = str(args[0]) if args else ""
    finished = private(save, "crossPromotionsFinished", [])
    if isinstance(finished, list) and game not in finished:
        finished.append(game)
    print("Cross promotion finished:", game)

def ping(save, args):
    print("Ping", "(game mode " + str(args[0]) + ")" if args else "")

def system_set_count_hack(save, args):
    # Speed hack detected by the client, which increments privateState.countHack.
    ps = save["privateState"]
    ps["countHack"] = _int(ps.get("countHack")) + 1
    print("Speed hack warning #", ps["countHack"], sep="")

HANDLERS = {
    "attack_player": attack_player,
    "end_attack": end_attack,
    "set_attack_team": set_attack_team,
    "buy_attacks_pack": buy_attacks_pack,
    "buy_spyings_pack": buy_spyings_pack,
    "spy_player": spy_player,
    "buy_pvp_territory": buy_pvp_territory,
    "clean_attacks": clean_attacks,
    "clean_received_assists": clean_received_assists,
    "modify_position_univers": modify_position_univers,
    "reset_position_univers": reset_position_univers,
    "reset_world_change": reset_world_change,
    "start_heavy_siege": start_heavy_siege,
    "reset_heavy_siege": reset_heavy_siege,
    "start_survival": start_survival,
    "end_survival": end_survival,
    "buy_survival_map": buy_survival_map,
    "add_survival_vida_extra": add_survival_vida_extra,
    "tournament_substract_resources": tournament_substract_resources,
    "tournament_refund_resources": tournament_refund_resources,
    "apply_rewards_ranking": apply_rewards_ranking,
    "assist_neighbor": assist_neighbor,
    "assist_neighbor_new": assist_neighbor_new,
    "assist_receive": assist_receive,
    "assist_send_feed": assist_send_feed,
    "accept_collect_help": accept_collect_help,
    "set_help_map": set_help_map,
    "set_fake_neighbors": set_fake_neighbors,
    "cross_promotion_finished": cross_promotion_finished,
    "ping": ping,
    "system_set_count_hack": system_set_count_hack,
}
