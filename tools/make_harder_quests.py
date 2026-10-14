"""Builds the optional harder quest islands (villages/quests_hard) from the originals (villages/quests).

Idea from LuisAlbertoMK's fork, redone for this version's islands and kept close to the game:
- only the common soldiers of an island are changed (unit types that appear at least twice on it),
  never its unique units (chiefs, bosses, mission characters);
- a soldier is replaced, at the same place, by a stronger soldier of the same race, flying the same
  way, taken among the units the game itself already uses as quest defenders;
- per island at most 40% of the soldiers change, and the total attack grows by at most 50%
  (life by at most 100%), so an island is harder, not impossible.

The originals are never modified. The server uses the harder islands only when
"harder_quests" is true in server_config.json (section "misc").

Usage: python tools/make_harder_quests.py [--dry-run]
"""
import argparse
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTS = os.path.join(ROOT, "villages", "quests")
OUT = os.path.join(ROOT, "villages", "quests_hard")
CONFIG = os.path.join(ROOT, "config", "main.json")

SHARE = 0.40
ATTACK_GROWTH = 1.5
LIFE_GROWTH = 2.0


def num(item, field):
	try:
		return int(float(item.get(field) or 0))
	except (TypeError, ValueError):
		return 0


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--dry-run", action="store_true")
	args = parser.parse_args()

	with open(CONFIG, encoding="utf-8") as f:
		items = {str(i["id"]): i for i in json.load(f)["items"]}

	def is_unit(entry):
		return isinstance(entry, list) and len(entry) >= 5 and items.get(str(entry[0]), {}).get("type") == "u"

	islands = {}
	for path in sorted(glob.glob(os.path.join(QUESTS, "*.save.json"))):
		with open(path, encoding="utf-8") as f:
			islands[path] = json.load(f)

	# pool: units the game itself uses as common quest soldiers
	pool = collections.defaultdict(set)	# (race, flying) -> unit ids
	for island in islands.values():
		for town in island["maps"]:
			counts = collections.Counter(str(e[0]) for e in town.get("items", []) if is_unit(e))
			for uid, n in counts.items():
				if n >= 2:
					u = items[uid]
					pool[(u.get("race"), str(u.get("flying")))].add(uid)

	def stronger(uid):
		"Stronger soldiers of the same race and kind, weakest first."
		u = items[uid]
		candidates = [c for c in pool[(u.get("race"), str(u.get("flying")))]
			if num(items[c], "attack") > num(u, "attack") and num(items[c], "life") >= num(u, "life")]
		return sorted(candidates, key=lambda c: (num(items[c], "attack"), num(items[c], "life")))

	os.makedirs(OUT, exist_ok=True)
	changed_islands = 0
	print(f"{'ile':<22} {'soldats':>7} {'changes':>7} {'attaque':>16} {'vie':>16}")
	for path, island in islands.items():
		changed = 0
		for town in island["maps"]:
			entries = [e for e in town.get("items", []) if is_unit(e)]
			counts = collections.Counter(str(e[0]) for e in entries)
			soldiers = [e for e in entries if counts[str(e[0])] >= 2]
			if not soldiers:
				continue
			attack0 = sum(num(items[str(e[0])], "attack") for e in entries)
			life0 = sum(num(items[str(e[0])], "life") for e in entries)
			attack, life = attack0, life0
			limit = int(len(soldiers) * SHARE)
			town_changed = 0
			for e in sorted(soldiers, key=lambda e: (num(items[str(e[0])], "attack"), num(items[str(e[0])], "life"))):
				if town_changed >= limit:
					break
				# the strongest replacement that still fits the island's budget
				new = None
				for c in stronger(str(e[0])):
					da_c = num(items[c], "attack") - num(items[str(e[0])], "attack")
					dl_c = num(items[c], "life") - num(items[str(e[0])], "life")
					if attack + da_c <= attack0 * ATTACK_GROWTH and life + dl_c <= life0 * LIFE_GROWTH:
						new, da, dl = c, da_c, dl_c
				if new is None:
					continue
				e[0] = int(new)
				attack += da
				life += dl
				changed += 1
				town_changed += 1
			name = os.path.basename(path)
			if town_changed:
				print(f"{name:<22} {len(soldiers):>7} {town_changed:>7} {attack0:>7} -> {attack:<6} {life0:>7} -> {life:<6}")
		if changed:
			changed_islands += 1
			if not args.dry_run:
				with open(os.path.join(OUT, os.path.basename(path)), "w", encoding="utf-8") as f:
					json.dump(island, f, indent="\t")
	print(f"\niles plus dures : {changed_islands} / {len(islands)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
