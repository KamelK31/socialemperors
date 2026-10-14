import json
import os
import copy
import uuid
import random
import shutil
import threading
import time
from flask import session
# from flask_session import SqlAlchemySessionInterface, current_app

from version import version_code
from engine import timestamp_now
from version import migrate_loaded_save
from constants import Constant

from bundle import VILLAGES_DIR, SAVES_DIR

__villages = {}  # ALL static neighbors
'''__villages = {
    "USERID_1": {
        "playerInfo": {...},
        "maps": [{...},{...}]
        "privateState": {...}
    },
    "USERID_2": {...}
}'''

__saves = {}  # ALL saved villages
'''__saves = {
    "USERID_1": {
        "playerInfo": {...},
        "maps": [{...},{...}]
        "privateState": {...}
    },
    "USERID_2": {...}
}'''

__initial_village = json.load(open(os.path.join(VILLAGES_DIR, "initial.json"), encoding="utf-8"))

# One lock for every read/write of the villages in memory and on disk.
# Flask serves requests on several threads: without it, two requests could write
# the same save file at the same time and leave it half-written (corrupted).
save_lock = threading.RLock()

BACKUPS_DIR = os.path.join(SAVES_DIR, "backups")
BACKUP_EVERY_SECONDS = 10 * 60  # one dated backup per village at most every 10 minutes
BACKUPS_TO_KEEP = 30            # older dated backups are deleted

def _read_village_file(path: str):
    "Returns the village stored in the file, or None if it can't be read or isn't a valid village."
    try:
        with open(path, encoding="utf-8") as f:
            village = json.load(f)
    except Exception:
        return None
    try:
        return village if is_valid_village(village) else None
    except Exception:
        return None

def _recover_village(file: str):
    "Tries the .bak copy, then the dated backups (newest first). Returns (village, source) or (None, None)."
    candidates = [os.path.join(SAVES_DIR, file + ".bak")]
    userid = file[:-len(".save.json")]
    backup_dir = os.path.join(BACKUPS_DIR, userid)
    if os.path.isdir(backup_dir):
        candidates += [os.path.join(backup_dir, b) for b in sorted(os.listdir(backup_dir), reverse=True) if b.endswith(".save.json")]
    for path in candidates:
        if os.path.exists(path):
            village = _read_village_file(path)
            if village is not None:
                return village, path
    return None, None

# Load saved villages

def load_saved_villages():
    with save_lock:
        _load_saved_villages()

def _load_saved_villages():
    global __villages
    global __saves
    # Empty in memory
    __villages = {}
    __saves = {}
    # Saves dir check
    if not os.path.exists(SAVES_DIR):
        try:
            print(f"Creating '{SAVES_DIR}' folder...")
            os.mkdir(SAVES_DIR)
        except:
            print(f"Could not create '{SAVES_DIR}' folder.")
            exit(1)
    if not os.path.isdir(SAVES_DIR):
        print(f"'{SAVES_DIR}' is not a folder... Move the file somewhere else.")
        exit(1)
    # Static neighbors in /villages
    for file in os.listdir(VILLAGES_DIR):
        if file == "initial.json" or not file.endswith(".json"):
            continue
        print(f" * Loading static neighbour {file}... ", end='')
        village = _read_village_file(os.path.join(VILLAGES_DIR, file))
        if village is None:
            print("Invalid neighbour")
            continue
        USERID = village["playerInfo"]["pid"]
        if str(USERID) in __villages:
            print(f"Ignored: duplicated PID '{USERID}'.")
        else:
            __villages[str(USERID)] = village
            print("Ok.")
    # Saves in /saves
    for file in os.listdir(SAVES_DIR):
        if not file.endswith(".save.json"):
            continue
        print(f" * Loading save at {file}... ", end='')
        save = _read_village_file(os.path.join(SAVES_DIR, file))
        restored = False
        if save is None:
            print("Corrupted or invalid save! ", end='')
            save, source = _recover_village(file)
            if save is None:
                print("No backup found, skipped.")
                continue
            print(f"Restored from backup '{source}'. ", end='')
            restored = True
        USERID = save["playerInfo"]["pid"]
        try:
            map_name = save["playerInfo"]["map_names"][ save["playerInfo"]["default_map"] ]
        except:
            map_name = '?'
        print(f"({map_name}) Ok.")
        __saves[str(USERID)] = save
        modified = migrate_loaded_save(save) # check save version for migration
        if modified or restored:
            save_session(str(USERID))
    

# New village

def new_village() -> str:
    # Generate USERID
    USERID: str = str(uuid.uuid4())
    assert USERID not in all_userid()
    # Copy init
    village = copy.deepcopy(__initial_village)
    # Custom values
    village["version"] = version_code
    village["playerInfo"]["pid"] = USERID
    village["maps"][0]["timestamp"] = timestamp_now()
    village["privateState"]["dartsRandomSeed"] = abs(int((2**16 - 1) * random.random()))
    # Memory saves
    __saves[USERID] = village
    # Generate save file
    save_session(USERID)
    print("Done.")
    return USERID

# Access functions

def all_saves_userid() -> list:
    "Returns a list of the USERID of every saved village."
    return list(__saves.keys())

def all_userid() -> list:
    "Returns a list of the USERID of every village."
    return list(__villages.keys()) + list(__saves.keys())

def save_info(USERID: str) -> dict:
    save = __saves[USERID]
    default_map = save["playerInfo"]["default_map"]
    empire_name = str(save["playerInfo"]["map_names"][default_map])
    xp = save["maps"][default_map]["xp"]
    level = save["maps"][default_map]["level"]
    return{"userid": USERID, "name": empire_name, "xp": xp, "level": level}

def all_saves_info() -> list:
    saves_info = []
    for userid in __saves:
        saves_info.append(save_info(userid))
    return list(saves_info)

def session(USERID: str) -> dict:
    assert(isinstance(USERID, str))
    return __saves[USERID] if USERID in __saves else None

def neighbor_session(USERID: str) -> dict:
    assert(isinstance(USERID, str))
    if USERID in __saves:
        return __saves[USERID]
    if USERID in __villages:
        return __villages[USERID]

def fb_friends_str(USERID: str) -> list:
    DELETE_ME = [{"uid": "1111", "pic_square":"http://127.0.0.1:5050/img/profile/Paladin_Justiciero.jpg"},
        {"uid": "aa_002", "pic_square":"/1025.png"}]
    friends = []
    # static villages
    for key in __villages:
        vill = __villages[key]
        # Avoid Arthur being loaded as friend.
        if vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_1 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_2 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_3:
            continue
        frie = {}
        frie["uid"] = vill["playerInfo"]["pid"]
        frie["pic_square"] = vill["playerInfo"]["pic"]
        if not frie["pic_square"]: frie["pic_square"] = "/img/profile/1025.png"
        friends += [frie]
    # other players
    for key in __saves:
        vill = __saves[key]
        if vill["playerInfo"]["pid"] == USERID:
            continue
        frie = {}
        frie["uid"] = vill["playerInfo"]["pid"]
        frie["pic_square"] = vill["playerInfo"]["pic"]
        if not frie["pic_square"]: frie["pic_square"] = "/img/profile/1025.png"
        friends += [frie]
    return friends

def neighbors(USERID: str) -> list:
    neighbors = []
    # static villages
    for key in __villages:
        vill = __villages[key]
        # Avoid Arthur being loaded as multiple neigtbors.
        if vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_1 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_2 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_3:
            continue
        neigh = dict(vill["playerInfo"]) # copy: don't write these stats into the village itself
        neigh["coins"] = vill["maps"][0]["coins"]
        neigh["xp"] = vill["maps"][0]["xp"]
        neigh["level"] = vill["maps"][0]["level"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neigh["wood"] = vill["maps"][0]["wood"]
        neigh["food"] = vill["maps"][0]["food"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neighbors += [neigh]
    # other players
    for key in __saves:
        vill = __saves[key]
        if vill["playerInfo"]["pid"] == USERID:
            continue
        neigh = dict(vill["playerInfo"]) # copy: don't write these stats into the village itself
        neigh["coins"] = vill["maps"][0]["coins"]
        neigh["xp"] = vill["maps"][0]["xp"]
        neigh["level"] = vill["maps"][0]["level"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neigh["wood"] = vill["maps"][0]["wood"]
        neigh["food"] = vill["maps"][0]["food"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neighbors += [neigh]
    return neighbors

# Check for valid village
# The reason why this was implemented is to warn the user if a save game from Social Wars was used by accident

def is_valid_village(save: dict):
    if "playerInfo" not in save or "maps" not in save or "privateState" not in save:
        # These are obvious
        return False
    for map in save["maps"]:
        if "oil" in map or "steel" in map:
            return False
        if "stone" not in map or "food" not in map:
            return False
        if "items" not in map:
            return False
        if type(map["items"]) != list:
            return False

    return True

# Persistency

def backup_session(USERID: str, force: bool = False):
    "Keeps dated copies of the save in saves/backups/<USERID>/ (at most one every 10 minutes, the newest 30 are kept)."
    with save_lock:
        source = os.path.join(SAVES_DIR, f"{USERID}.save.json")
        if not os.path.exists(source):
            return
        backup_dir = os.path.join(BACKUPS_DIR, USERID)
        os.makedirs(backup_dir, exist_ok=True)
        backups = sorted(b for b in os.listdir(backup_dir) if b.endswith(".save.json"))
        if backups and not force:
            last = os.path.getmtime(os.path.join(backup_dir, backups[-1]))
            if time.time() - last < BACKUP_EVERY_SECONDS:
                return
        name = time.strftime("%Y%m%d-%H%M%S") + ".save.json"
        shutil.copy2(source, os.path.join(backup_dir, name))
        backups.append(name)
        for old in sorted(set(backups))[:-BACKUPS_TO_KEEP]:
            try:
                os.remove(os.path.join(backup_dir, old))
            except OSError:
                pass

def save_session(USERID: str):
    file = f"{USERID}.save.json"
    print(f" * Saving village at {file}... ", end='')
    with save_lock:
        village = session(USERID)
        if village is None:
            print("Unknown village, not saved.")
            return
        path = os.path.join(SAVES_DIR, file)
        tmp_path = path + ".tmp"
        # 1. Write the whole save to a temporary file and make sure it reached the disk.
        with open(tmp_path, 'w', encoding="utf-8") as f:
            json.dump(village, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        # 2. Keep the previous good save as .bak.
        if os.path.exists(path):
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass
        # 3. Swap the new save in, in one step: the save file is never left half-written,
        #    even if the server window is closed in the middle of a save.
        for attempt in range(10):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                # Windows: an antivirus or file indexer may hold the file for a moment
                if attempt == 9:
                    raise
                time.sleep(0.1)
        try:
            backup_session(USERID)
        except OSError as e:
            print(f"(backup failed: {e}) ", end='')
    print("Done.")
