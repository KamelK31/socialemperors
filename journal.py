"""Error journal and recent server log.

- journal-erreurs.txt: every action the server refused or crashed on, and every error the game
  reported, written in plain words. A refused action makes the game reload, so this is the list
  of the reloads and why they happened.
- recent_log_lines(): the last lines of the server log, kept in memory, for the bug reports.
"""
import collections
import json
import logging
import os
import threading
import time

from bundle import BASE_DIR

JOURNAL_PATH = os.path.join(BASE_DIR, "journal-erreurs.txt")
JOURNAL_MAX_BYTES = 2 * 1024 * 1024  # then renamed to journal-erreurs.old.txt and a new one starts

_lock = threading.Lock()
_recent = collections.deque(maxlen=3000)


class _RecentLinesHandler(logging.Handler):
	def emit(self, record):
		try:
			_recent.append(self.format(record))
		except Exception:
			pass


def install_recent_log(logger):
	handler = _RecentLinesHandler()
	handler.setLevel(logging.INFO)
	handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s', "%Y-%m-%d %H:%M:%S"))
	logger.addHandler(handler)


def recent_log_lines():
	return list(_recent)


def _short(value, limit=600):
	try:
		text = json.dumps(value, ensure_ascii=False)
	except (TypeError, ValueError):
		text = str(value)
	return text if len(text) <= limit else text[:limit] + " ..."


def write(kind, player, what, detail=""):
	"""kind: REFUSE (the server said no, the game reloads), PLANTAGE (server error, the game reloads),
	INCONNU (action the server doesn't know, ignored), JEU (error reported by the game itself)."""
	line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {kind:<8} {player} : {what}"
	if detail:
		line += "\n    " + str(detail).strip().replace("\n", "\n    ")
	with _lock:
		try:
			if os.path.exists(JOURNAL_PATH) and os.path.getsize(JOURNAL_PATH) > JOURNAL_MAX_BYTES:
				os.replace(JOURNAL_PATH, os.path.join(BASE_DIR, "journal-erreurs.old.txt"))
			new_file = not os.path.exists(JOURNAL_PATH)
			with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
				if new_file:
					f.write("Journal des erreurs du serveur Social Empires\n"
						"REFUSE   = le serveur a refuse une action : le jeu recharge.\n"
						"PLANTAGE = erreur du serveur sur une action : le jeu recharge.\n"
						"INCONNU  = action que le serveur ne connait pas (ignoree).\n"
						"JEU      = erreur signalee par le jeu lui-meme.\n\n")
				f.write(line + "\n")
		except OSError:
			pass


def command_failed(kind, player_name, cmd, args, detail=""):
	write(kind, player_name, f"{cmd} {_short(args)}", detail)


def journal_tail(max_lines=200):
	try:
		with open(JOURNAL_PATH, encoding="utf-8") as f:
			return f.readlines()[-max_lines:]
	except OSError:
		return []
