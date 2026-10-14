"""Mise a jour du jeu depuis GitHub (branche "mon-jeu" de KamelK31/socialemperors), sans git.

- Compare la version installee (version-installee.json) avec la derniere version publiee, et ne
  telecharge que les fichiers qui ont change depuis : tes parties et tes reglages ne sont jamais ecrases.
- Avant de remplacer un fichier, l'ancien est copie dans ancienne-version/<date>/ (pour revenir en arriere).
- server_config.json : tes reglages sont gardes, seuls les nouveaux reglages sont ajoutes.
- Dit aussi si Nerroth a publie des nouveautes qui ne sont pas encore dans ta version.

Lancer avec "METTRE A JOUR.bat", serveur ferme.
"""
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import urllib.parse
import urllib.request

REPO = "KamelK31/socialemperors"
BRANCH = "mon-jeu"
NERROTH_REPO = "AcidCaos/socialemperors"
NERROTH_BRANCH = "nerroth-rewrite"

BASE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(BASE, "version-installee.json")
NEVER_TOUCHED = ("saves/", "enemy/", "friend/", "logs/", "cache/", "download_assets/", "python/",
	"rapports-bugs/", "ancienne-version/", "build/", "distr/", "__pycache__/")
NEVER_TOUCHED_FILES = ("METTRE A JOUR.bat", "journal-erreurs.txt", "journal-erreurs.old.txt", "version-installee.json")
CONFIG = "server_config.json"


def get_json(url):
	req = urllib.request.Request(url, headers={"User-Agent": "social-empires-updater", "Accept": "application/vnd.github+json"})
	with urllib.request.urlopen(req, timeout=60) as r:
		return json.load(r)


def get_bytes(url):
	req = urllib.request.Request(url, headers={"User-Agent": "social-empires-updater"})
	with urllib.request.urlopen(req, timeout=120) as r:
		return r.read()


def git_blob_sha(path):
	h = hashlib.sha1()
	h.update(b"blob %d\0" % os.path.getsize(path))
	with open(path, "rb") as f:
		for chunk in iter(lambda: f.read(1 << 20), b""):
			h.update(chunk)
	return h.hexdigest()


def skipped(path):
	return path.startswith(NEVER_TOUCHED) or path in NEVER_TOUCHED_FILES


def server_running():
	with socket.socket() as s:
		s.settimeout(0.5)
		return s.connect_ex(("127.0.0.1", 5050)) == 0


def merge_config(user, new):
	"New settings are added, the player's values are kept."
	if isinstance(user, dict) and isinstance(new, dict):
		merged = dict(new)
		for k, v in user.items():
			merged[k] = merge_config(v, new[k]) if k in new else v
		return merged
	return user


def main():
	print("Mise a jour de Social Empires")
	print("=============================\n")
	if server_running():
		print("Le serveur du jeu est ouvert. Clique sur \"Quitter\" dans le jeu, puis relance la mise a jour.")
		return 1

	print("Recherche de la derniere version...")
	try:
		head = get_json(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}")
		commit = head["sha"]
		tree = get_json(f"https://api.github.com/repos/{REPO}/git/trees/{commit}?recursive=1")
	except Exception as e:
		print(f"Impossible de joindre GitHub ({e}). Verifie ta connexion internet.")
		return 1
	if tree.get("truncated"):
		print("La liste des fichiers recue de GitHub est incomplete, mise a jour annulee.")
		return 1
	remote = {t["path"]: t["sha"] for t in tree["tree"] if t["type"] == "blob" and not skipped(t["path"])}

	installed = {}
	if os.path.exists(MANIFEST):
		with open(MANIFEST, encoding="utf-8") as f:
			installed = json.load(f)
	old_files = installed.get("files", {})

	if installed.get("commit") == commit:
		print("Tu as deja la derniere version.")
		changed, removed = [], []
	else:
		# changed upstream since the installed version, or missing here although never deleted by the player
		changed = []
		for path, sha in remote.items():
			local = os.path.join(BASE, *path.split("/"))
			if path in old_files and old_files[path] == sha:
				continue	# not changed upstream: the player's copy (or its absence) is kept
			if os.path.exists(local) and git_blob_sha(local) == sha:
				continue
			changed.append(path)
		removed = [p for p in old_files if p not in remote and not skipped(p) and os.path.exists(os.path.join(BASE, *p.split("/")))]

	if changed or removed:
		stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
		backup_root = os.path.join(BASE, "ancienne-version", stamp)
		print(f"{len(changed)} fichier(s) a mettre a jour, {len(removed)} a retirer.")
		for i, path in enumerate(changed, 1):
			local = os.path.join(BASE, *path.split("/"))
			print(f"  [{i}/{len(changed)}] {path}")
			try:
				data = get_bytes(f"https://raw.githubusercontent.com/{REPO}/{commit}/{urllib.parse.quote(path)}")
			except Exception as e:
				print(f"\nTelechargement impossible ({e}). Rien n'a ete casse : relance la mise a jour plus tard.")
				return 1
			if os.path.exists(local):
				dest = os.path.join(backup_root, *path.split("/"))
				os.makedirs(os.path.dirname(dest), exist_ok=True)
				shutil.copy2(local, dest)
			if path == CONFIG and os.path.exists(local):
				with open(local, encoding="utf-8") as f:
					user_cfg = json.load(f)
				data = (json.dumps(merge_config(user_cfg, json.loads(data.decode("utf-8"))), indent="\t", ensure_ascii=False) + "\n").encode("utf-8")
			os.makedirs(os.path.dirname(local) or BASE, exist_ok=True)
			with open(local + ".part", "wb") as f:
				f.write(data)
			os.replace(local + ".part", local)
		for path in removed:
			local = os.path.join(BASE, *path.split("/"))
			dest = os.path.join(backup_root, *path.split("/"))
			os.makedirs(os.path.dirname(dest), exist_ok=True)
			shutil.move(local, dest)
			print(f"  retire : {path}")
		print(f"\nMise a jour terminee. Les anciens fichiers sont dans ancienne-version\\{stamp}")
	elif installed.get("commit") != commit:
		print("Tes fichiers sont deja a jour.")

	with open(MANIFEST + ".part", "w", encoding="utf-8") as f:
		json.dump({"commit": commit, "files": remote}, f)
	os.replace(MANIFEST + ".part", MANIFEST)

	# Nerroth's own updates, not yet in this version
	try:
		nerroth = get_json(f"https://api.github.com/repos/{NERROTH_REPO}/commits/{NERROTH_BRANCH}")["sha"]
		with open(os.path.join(BASE, "NERROTH.txt"), encoding="utf-8") as f:
			integrated = f.read().split()[0]
		if nerroth != integrated:
			compare = get_json(f"https://api.github.com/repos/{NERROTH_REPO}/compare/{integrated}...{nerroth}")
			print(f"\nNerroth a publie {compare.get('ahead_by', '?')} nouveaute(s) pas encore dans ta version :")
			for c in compare.get("commits", [])[-15:]:
				print("  - " + c["commit"]["message"].splitlines()[0])
			print("Demande a Claude de les integrer, puis relance cette mise a jour.")
		else:
			print("\nRien de nouveau chez Nerroth.")
	except Exception as e:
		print(f"\n(Impossible de verifier les nouveautes de Nerroth : {e})")
	return 0


if __name__ == "__main__":
	code = main()
	sys.exit(code)
