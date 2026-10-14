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
