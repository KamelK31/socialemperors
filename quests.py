import json
import os
import logging

log = logging.getLogger('__main__')

from bundle import QUESTS_DIR

from server_config import get_server_config

# Optional harder islands (tools/make_harder_quests.py), used when "harder_quests" is true in server_config.json
HARD_QUESTS_DIR = os.path.join(os.path.dirname(QUESTS_DIR), "quests_hard")

def get_quest_map(questid):
	file = os.path.join(QUESTS_DIR, str(questid) + ".save.json")
	if get_server_config().get("misc", {}).get("harder_quests", False):
		harder = os.path.join(HARD_QUESTS_DIR, str(questid) + ".save.json")
		if os.path.exists(harder):
			file = harder
	if not os.path.exists(file):
		return None
	d = json.load(open(file, 'r'))
	return d