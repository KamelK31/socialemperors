"""Menu de triche pour les parties de test (/triche).

Il n'agit que sur les parties cochees "partie de test" (save["_partie_test"], jamais envoye au jeu), pour que les
vraies parties restent legit. Les changements sont faits dans la partie en memoire du serveur puis
enregistres ; le jeu les voit apres un rechargement (F5).
"""
import json
import logging
import time
from urllib.parse import quote

from flask import render_template, request, redirect

from get_game_config import get_game_config
from engine import map_add_item, timestamp_now
from bundle import VILLAGES_DIR
import os

log = logging.getLogger('__main__')

RESOURCES = (("cash", "Cash"), ("coins", "Or"), ("wood", "Bois"), ("stone", "Pierre"), ("food", "Nourriture"))


def _levels():
	return get_game_config()["levels"]


def max_level():
	# the last entry (2 billion XP) is a filler, not a real level: the game's XP bar needs a next level
	return len(_levels()) - 1


def xp_for_level(level):
	return int(_levels()[level - 1]["exp_required"])


def _items_for_menu():
	items = []
	for it in get_game_config()["items"]:
		if it.get("type") in ("u", "b"):
			items.append({"id": int(it["id"]), "n": str(it.get("name", "")), "t": it["type"]})
	items.sort(key=lambda x: x["n"].lower())
	return items


ALL_LANDS = [7, 8, 9, 12, 13, 14, 17, 18, 19]	# the 3x3 lands around the starting one (8 expansions)
CLEARABLE = ("125", "126", "127", "128")	# trees, stones, gold rocks, regenerating ones
PLAN_FILE = os.path.join(VILLAGES_DIR, "plan_grec.json")
PLAN_TOWN_HALL = (52, 52)


def _land(x, y):
	return (int(y) // 20) * 5 + (int(x) // 20) + 1


def _plan():
	halls = {int(it["id"]) for it in get_game_config()["items"] if it.get("subcat_functional") == "135"}
	with open(PLAN_FILE, encoding="utf-8") as f:
		return [p for p in json.load(f) if int(p["id"]) not in halls]


def _occupied(town, known):
	cells = set()
	for it in town.get("items", []):
		d = known.get(str(it[0]))
		if not d or d.get("type") != "b":
			continue
		w, h = int(d.get("width") or 1), int(d.get("height") or 1)
		for a in range(int(it[1]), int(it[1]) + w):
			for b in range(int(it[2]), int(it[2]) + h):
				cells.add((a, b))
	return cells


def is_test(save):
	return bool(save.get("_partie_test", False))


def register(app, s, same_site):

	def back(message="", error=""):
		target = "/triche"
		args = []
		uid = request.form.get("uid") or request.args.get("uid")
		if uid:
			args.append("uid=" + quote(uid))
		if message:
			args.append("message=" + quote(message))
		if error:
			args.append("erreur=" + quote(error))
		return redirect(target + ("?" + "&".join(args) if args else ""))

	@app.route("/triche")
	async def triche():
		games = []
		for uid in s.all_saves_userid():
			save = s.session(uid)
			town = save["maps"][int(save["playerInfo"].get("default_map", 0) or 0)]
			games.append({
				"uid": uid, "name": save["playerInfo"]["name"], "test": is_test(save),
				"level": town.get("level"), "cash": save["playerInfo"].get("cash", 0),
				"coins": town.get("coins", 0), "wood": town.get("wood", 0), "stone": town.get("stone", 0),
				"food": town.get("food", 0), "mana": save["privateState"].get("mana", 0),
				"potion": save["privateState"].get("potion", 0),
				"towns": [str(n) for n in save["playerInfo"].get("map_names", [])][:len(save["maps"])],
			})
		selected = request.args.get("uid") or (games[0]["uid"] if games else "")
		return render_template("triche.html", games=games, selected=selected, max_level=max_level(),
			items_json=json.dumps(_items_for_menu(), ensure_ascii=False).replace("</", "<\\/"),
			message=request.args.get("message", ""), error=request.args.get("erreur", ""))

	@app.route("/triche/test", methods=["POST"])
	async def triche_test():
		if not same_site():
			return ("", 403)
		uid = request.form.get("uid", "")
		with s.save_lock:
			save = s.session(uid)
			if save is None:
				return back(error="Partie inconnue.")
			on = request.form.get("on") == "1"
			save["_partie_test"] = on
			s.save_session(uid, False)
		return back("Partie marquée comme partie de test." if on else "Partie remise en partie normale : la triche est désactivée pour elle.")

	@app.route("/triche/appliquer", methods=["POST"])
	async def triche_appliquer():
		if not same_site():
			return ("", 403)
		uid = request.form.get("uid", "")
		action = request.form.get("action", "")
		with s.save_lock:
			save = s.session(uid)
			if save is None:
				return back(error="Partie inconnue.")
			if not is_test(save):
				return back(error="Cette partie n'est pas une partie de test : coche d'abord « partie de test ».")
			s.backup_session(uid, force=True)	# a restorable copy from before the cheat
			ps = save["privateState"]
			towns = save["maps"]
			done = ""
			try:
				if action == "ressources":
					for key, label in RESOURCES:
						value = request.form.get(key, "").strip()
						if value == "":
							continue
						value = max(0, min(int(float(value)), 2_000_000_000))
						if key == "cash":
							save["playerInfo"]["cash"] = value
						else:
							for town in towns:
								town[key] = value
					done = "Ressources mises à jour."
				elif action == "niveau":
					level = max(1, min(int(request.form.get("level", "1")), max_level()))
					for town in towns:
						town["level"] = level
						town["xp"] = xp_for_level(level)
					done = f"Niveau {level}."
				elif action == "mana":
					if request.form.get("mana", "").strip() != "":
						ps["mana"] = max(0, int(float(request.form["mana"])))
					if request.form.get("potion", "").strip() != "":
						ps["potion"] = max(0, int(float(request.form["potion"])))
					done = "Mana et potions mises à jour."
				elif action == "objet":
					item_id = str(int(request.form.get("item", "0")))
					qty = max(1, min(int(request.form.get("qty", "1")), 500))
					town_id = max(0, min(int(request.form.get("town", "0")), len(towns) - 1))
					known = {str(it["id"]): it for it in get_game_config()["items"]}
					if item_id not in known:
						return back(error="Objet inconnu.")
					store = towns[town_id].setdefault("store", {})
					store[item_id] = int(store.get(item_id, 0)) + qty
					done = f"{qty} × {known[item_id].get('name')} ajouté(s) à l'entrepôt."
				elif action == "quetes":
					for town in towns:
						town["questTimes"] = {}
						town["lastQuestTimes"] = []
					done = "Temps d'attente des quêtes remis à zéro."
				elif action == "terres":
					town = towns[0]
					town["expansions"] = sorted(set(ALL_LANDS) | set(int(e) for e in town.get("expansions", [])))
					done = "Les 9 terres autour de ton hôtel de ville sont à toi."
				elif action == "nettoyer":
					known = {str(it["id"]): it for it in get_game_config()["items"]}
					town = towns[0]
					owned = set([13] + [int(e) for e in town.get("expansions", [])])
					before = len(town["items"])
					town["items"] = [it for it in town["items"]
						if not (known.get(str(it[0]), {}).get("subcat_functional") in CLEARABLE and _land(it[1], it[2]) in owned)]
					done = f"{before - len(town['items'])} arbres et rochers retirés de tes terres."
				elif action == "plan_entrepot":
					store = towns[0].setdefault("store", {})
					total = 0
					for p in _plan():
						store[str(p["id"])] = int(store.get(str(p["id"]), 0)) + 1
						total += 1
					done = f"{total} bâtiments du plan grec ajoutés à l'entrepôt."
				elif action == "plan_construire":
					known = {str(it["id"]): it for it in get_game_config()["items"]}
					town = towns[0]
					hall = [it for it in town["items"] if known.get(str(it[0]), {}).get("subcat_functional") == "135"]
					if not hall:
						return back(error="Hôtel de ville introuvable.")
					dx, dy = int(hall[0][1]) - PLAN_TOWN_HALL[0], int(hall[0][2]) - PLAN_TOWN_HALL[1]
					owned = set([13] + [int(e) for e in town.get("expansions", [])])
					missing_lands = {_land(p["x"] + dx, p["y"] + dy) for p in _plan()} - owned
					if missing_lands:
						return back(error="Il te manque des terres : clique d'abord sur « Débloquer toutes les terres ».")
					# trees and rocks on the plan's spots go away
					cells = set()
					for p in _plan():
						for a in range(p["x"] + dx, p["x"] + dx + p["w"]):
							for b in range(p["y"] + dy, p["y"] + dy + p["h"]):
								cells.add((a, b))
					def blocks(it):
						d = known.get(str(it[0]), {})
						if d.get("subcat_functional") not in CLEARABLE:
							return False
						w, h = int(d.get("width") or 1), int(d.get("height") or 1)
						return any((a, b) in cells for a in range(int(it[1]), int(it[1]) + w) for b in range(int(it[2]), int(it[2]) + h))
					town["items"] = [it for it in town["items"] if not blocks(it)]
					taken = _occupied(town, known)
					built, skipped = 0, 0
					old = timestamp_now() - 365 * 86400	# already finished
					for p in _plan():
						x, y = p["x"] + dx, p["y"] + dy
						spot = {(a, b) for a in range(x, x + p["w"]) for b in range(y, y + p["h"])}
						if spot & taken:
							skipped += 1
							continue
						map_add_item(town, p["id"], x, y, timestamp=old, userid=save["playerInfo"]["pid"])
						taken |= spot
						built += 1
					done = f"Royaume grec construit : {built} bâtiments posés" + (f", {skipped} places déjà prises par tes bâtiments (laissées telles quelles)." if skipped else ".")
				elif action == "bouclier":
					ps["shieldEndTime"] = 0
					done = "Bouclier retiré."
				else:
					return back(error="Action inconnue.")
			except (ValueError, KeyError, IndexError) as e:
				return back(error=f"Valeur invalide ({e}).")
			s.save_session(uid, False)
			log.info(f" * TRICHE [{save['playerInfo']['name']}] {action}: {done}")
		return back(done + " Recharge le jeu (F5) pour le voir.")
