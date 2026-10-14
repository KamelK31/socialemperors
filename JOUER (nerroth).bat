@echo off
title Social Empires - serveur
cd /d "%~dp0"

if not exist "python\python.exe" (
    echo Python est introuvable dans le dossier "python" du jeu.
    goto erreur
)
if not exist "assets\flash\SocialEmpires1.4.07sec_fixed.swf" (
    echo Le fichier du jeu assets\flash\SocialEmpires1.4.07sec_fixed.swf est introuvable.
    goto erreur
)

rem --- Serveur deja ouvert : on ouvre juste le jeu ---
netstat -ano | find "127.0.0.1:5050 " | find "LISTENING" >nul
if not errorlevel 1 (
    echo Le serveur est deja ouvert : ouverture du jeu...
    start "" "http://127.0.0.1:5050/jouer"
    timeout /t 3 >nul
    exit /b 0
)

echo.
echo  Social Empires : le jeu s'ouvre dans ton navigateur.
echo  Laisse cette fenetre ouverte pendant que tu joues.
echo  Pour quitter : bouton "Quitter" au-dessus du jeu (ta partie est enregistree
echo  et cette fenetre se ferme toute seule).
echo.
"python\python.exe" -X utf8 server.py
if errorlevel 1 goto erreur
exit /b 0

:erreur
echo.
echo Le serveur s'est arrete sur une erreur. Fais une capture de cette fenetre pour Claude.
pause
exit /b 1
