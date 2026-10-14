"""Extra pages and helpers of this install (all in French, for the player):

/jouer                one click play: logs into the last played game with the 1.4.07 client in Ruffle
/quitter              saves every game, then stops the server
/sauvegardes          dated backups of each game, restore one in one click
/bug                  bug report: a zip with the description, the recent server log, the error journal and the game
/ruffle/<file>        the Ruffle player shipped with the game (no internet needed, no surprise update)
asset_version(name)   number that changes when a game file changes, so the browser never keeps an old copy
+ gzip of the big text answers (game config, player info)
"""
import gzip
import io
import mimetypes
import json
import logging
import os
import threading
import time
import zipfile
from urllib.parse import quote

from flask import render_template, request, redirect, send_from_directory, session as flasksession

import journal
from bundle import ASSETS_DIR, TEMPLATES_DIR, BASE_DIR
from server_config import get_server_config

log = logging.getLogger('__main__')

# Windows may not know these: Ruffle needs the right type to start quickly
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".js")

GAME_SWF = "SocialEmpires1.4.07sec_fixed.swf"
RUFFLE_DIR = os.path.join(TEMPLATES_DIR, "ruffle")
BUG_REPORTS_DIR = os.path.join(BASE_DIR, "rapports-bugs")
APP_VERSION_FILE = os.path.join(BASE_DIR, "VERSION.txt")

GZIP_MIN_BYTES = 16 * 1024
GZIP_TYPES = ("text/", "application/json", "application/javascript", "application/x-www-form-urlencoded")


def app_version():
	try:
		with open(APP_VERSION_FILE, encoding="utf-8") as f:
			return f.read().strip()
	except OSError:
		return "?"


def asset_version(name):
	"Modification time of a game file in assets/flash: part of its URL, so a changed file is always fetched again."
	try:
		return str(int(os.path.getmtime(os.path.join(ASSETS_DIR, "flash", name))))
	except OSError:
		return "0"


def _french_date(backup_name):
	# 20261014-163512.save.json -> 14/10/2026 16:35
	try:
		t = time.strptime(backup_name[:15], "%Y%m%d-%H%M%S")
		return time.strftime("%d/%m/%Y %H:%M", t)
	except ValueError:
		return backup_name


def _summary(save):
	try:
		default_map = int(save["playerInfo"].get("default_map", 0))
		town = save["maps"][default_map]
		return {
			"level": town.get("level", "?"),
			"xp": town.get("xp", 0),
			"gold": town.get("coins", 0),
			"cash": save["playerInfo"].get("cash", 0),
			"items": len(town.get("items", [])),
		}
	except (KeyError, IndexError, TypeError, ValueError):
		return {"level": "?", "xp": "?", "gold": "?", "cash": "?", "items": "?"}


def register(app, sessions_module, host, port):
	s = sessions_module

	def same_site():
		"Actions that change something only come from the game's own pages (not from another web site)."
		source = request.headers.get("Origin") or request.headers.get("Referer") or ""
		if not source:
			return True
		allowed = (f"http://{host}:{port}", f"http://localhost:{port}", f"http://127.0.0.1:{port}")
		return source.startswith(allowed)

	app.jinja_env.globals["asset_version"] = asset_version
	app.jinja_env.globals["app_version"] = app_version

	# -- gzip of the big text answers ------------------------------------------------------------------
	@app.after_request
	def _gzip(response):
		try:
			if response.direct_passthrough or response.status_code != 200:
				return response
			if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
				return response
			if response.headers.get("Content-Encoding"):
				return response
			if not (response.mimetype or "").startswith(GZIP_TYPES):
				return response
			data = response.get_data()
			if len(data) < GZIP_MIN_BYTES:
				return response
			response.set_data(gzip.compress(data, compresslevel=5))
			response.headers["Content-Encoding"] = "gzip"
			response.headers["Content-Length"] = str(len(response.get_data()))
			response.headers.add("Vary", "Accept-Encoding")
		except Exception as e:
			log.warning(f" * gzip skipped: {e}")
		return response

	# -- Ruffle shipped with the game --------------------------------------------------------------
	@app.route("/ruffle/<path:path>")
	async def ruffle_files(path):
		return send_from_directory(RUFFLE_DIR, path, max_age=7 * 24 * 3600)

	# -- one click play --------------------------------------------------------------------------------
	@app.route("/jouer")
	async def jouer():
		saves = [(s.session(uid)["playerInfo"].get("last_logged_in", 0) or 0, uid) for uid in s.all_saves_userid()]
		if not saves:
			return redirect("/")
		saves.sort(key=lambda x: int(x[0]), reverse=True)
		uid = saves[0][1]
		flasksession['USERID'] = uid
		flasksession['GAMEVERSION'] = GAME_SWF
		flasksession['RUNNER'] = "RUFFLE"
		log.info(f"[JOUER] USERID={uid}")
		return redirect("/play/ruffle")

	# -- quit cleanly -----------------------------------------------------------------------------------
	@app.route("/quitter", methods=["GET", "POST"])
	async def quitter():
		if request.method == "GET":
			return render_template("quitter.html", done=False)
		if not same_site():
			return ("", 403)
		s.save_all_sessions()
		log.info(" * Every game saved, the server stops.")
		# answer first, then stop
		threading.Timer(1.0, lambda: os._exit(0)).start()
		return render_template("quitter.html", done=True)

	# -- backups ----------------------------------------------------------------------------------------
	@app.route("/sauvegardes")
	async def sauvegardes():
		players = []
		for uid in s.all_saves_userid():
			save = s.session(uid)
			backups = [{"name": name, "date": _french_date(name), **_summary(b)} for name, b in s.list_backups(uid)]
			players.append({"uid": uid, "name": save["playerInfo"]["name"], "current": _summary(save), "backups": backups})
		mirror = s.mirror_dir()
		return render_template("sauvegardes.html", players=players, mirror=mirror,
			message=request.args.get("message", ""), error=request.args.get("erreur", ""))

	@app.route("/sauvegardes/restaurer", methods=["POST"])
	async def sauvegardes_restaurer():
		if not same_site():
			return ("", 403)
		uid = request.form.get("uid", "")
		name = request.form.get("backup", "")
		if s.restore_backup(uid, name):
			return redirect("/sauvegardes?message=" + quote(f"Partie restaurée à la copie du {_french_date(name)}. Recharge le jeu (F5) s'il est ouvert."))
		return redirect("/sauvegardes?erreur=" + quote("Cette copie n'a pas pu être restaurée."))

	@app.route("/sauvegardes/maintenant", methods=["POST"])
	async def sauvegardes_maintenant():
		if not same_site():
			return ("", 403)
		uid = request.form.get("uid", "")
		if s.session(uid) is None:
			return redirect("/sauvegardes?erreur=" + quote("Partie inconnue."))
		s.save_session(uid, False)
		s.backup_session(uid, force=True)
		return redirect("/sauvegardes?message=" + quote("Copie créée."))

	# -- bug report -------------------------------------------------------------------------------------
	@app.route("/bug", methods=["GET", "POST"])
	async def bug():
		uid = flasksession.get("USERID")
		if request.method == "GET":
			return render_template("bug.html", done=False, path="")
		if not same_site():
			return ("", 403)
		description = request.form.get("description", "").strip()
		os.makedirs(BUG_REPORTS_DIR, exist_ok=True)
		name = time.strftime("bug-%Y%m%d-%H%M%S") + ".zip"
		path = os.path.join(BUG_REPORTS_DIR, name)
		with s.save_lock:
			buf = io.BytesIO()
			with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
				z.writestr("description.txt", description or "(pas de description)")
				z.writestr("infos.txt", f"version: {app_version()}\njeu: {GAME_SWF}\ndate: {time.strftime('%Y-%m-%d %H:%M:%S')}\njoueur: {uid}\n")
				z.writestr("serveur-recent.log", "\n".join(journal.recent_log_lines()))
				z.writestr("journal-erreurs.txt", "".join(journal.journal_tail(500)))
				z.writestr("server_config.json", json.dumps(get_server_config(), indent="\t"))
				for player in s.all_saves_userid():
					if uid is None or player == uid:
						z.writestr(f"partie-{player}.save.json", json.dumps(s.session(player), indent="\t"))
			with open(path, "wb") as f:
				f.write(buf.getvalue())
		log.info(f" * Bug report written: {path}")
		if os.name == "nt":
			try:
				os.startfile(os.path.abspath(BUG_REPORTS_DIR))
			except OSError:
				pass
		return render_template("bug.html", done=True, path=os.path.abspath(path))

	# -- open the browser when the server is ready ----------------------------------------------------
	def open_browser():
		if not get_server_config().get("server", {}).get("open_browser", True):
			return
		import webbrowser
		url = f"http://{host}:{port}/jouer"
		def _open():
			time.sleep(1.5)
			try:
				webbrowser.open(url)
			except Exception:
				pass
		threading.Thread(target=_open, daemon=True).start()

	return open_browser
