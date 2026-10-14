from sessions import session, neighbor_session, neighbors
from engine import timestamp_now

def get_player_info(USERID):
    # Update last logged in
    ts_now = timestamp_now()
    session(USERID)["playerInfo"]["last_logged_in"] = ts_now
    # The island selector reads privateState.maps (race of each island); older saves don't have it.
    save = session(USERID)
    towns = save["privateState"].get("maps")
    if not isinstance(towns, list) or len(towns) < len(save["maps"]):
        towns = towns if isinstance(towns, list) else []
        while len(towns) < len(save["maps"]):
            towns.append({"r": save["maps"][len(towns)].get("race", "h")})
        save["privateState"]["maps"] = towns
    # player
    player_info = {
        "result": "ok",
        "processed_errors": 0,
        "timestamp": ts_now,
        "playerInfo": session(USERID)["playerInfo"],
        "map": session(USERID)["maps"][0],
        "privateState": session(USERID)["privateState"],
        "neighbors": neighbors(USERID)
    }
    return player_info

def get_neighbor_info(userid, map_number):
    neighbor_info = {
        "result": "ok",
        "processed_errors": 0,
        "timestamp": timestamp_now(),
        "playerInfo": neighbor_session(userid)["playerInfo"],
        "map": neighbor_session(userid)["maps"][map_number],
        "privateState": neighbor_session(userid)["privateState"],
        "neighbors": neighbors(userid)
    }
    return neighbor_info
