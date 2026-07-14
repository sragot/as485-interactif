#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
maj_gui.py — Interface graphique de mise a jour (Tkinter, sans dependance).
===========================================================================
Petite fenetre pour regenerer les donnees et le tableau de bord sans ligne de
commande. Un bouton par etape (1 -> 5) + un bouton « Tout faire ». Le journal
s'affiche en direct.

Pipeline :
  1. Harmoniser AS485 (onglets Stats.xlsx + CSV bruts AS485_BD_*.csv)
  2. Reconstruire la base SQLite (40_base/sqdi_sante.db)
  3. Exporter les indicateurs du dashboard (JSON)
  4. Generer le dashboard HTML autonome
  5. Publier : copier le dashboard dans docs/ (GitHub Pages)

Pour ajouter un exercice AS485 : deposer « AS485_BD_AAAA-AAAA.csv » dans
« Demographic Data/ » (ou un onglet AAAA-AAAA dans Stats.xlsx), puis « Tout faire ».

Lancement :
    python 10_scripts/maj_gui.py
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, scrolledtext

RACINE = Path(__file__).resolve().parent.parent
SCRIPTS = RACINE / "10_scripts"
PY = sys.executable or "python"

DASH_SRC = RACINE / "50_publication" / "dashboard_as485.html"
DASH_DST = RACINE / "docs" / "dashboard.html"


def _cmd(*script_args) -> list:
    return [PY, str(SCRIPTS / script_args[0]), *script_args[1:]]


# (libelle, callable_or_cmd). Une commande = liste passee a subprocess ;
# un callable(log) = etape interne (ex. copie de fichiers).
ETAPES = [
    ("1. Harmoniser AS485 (Stats.xlsx + CSV bruts)", _cmd("harmoniser_as485.py")),
    ("2. Reconstruire la base SQLite", _cmd("construire_base.py")),
    ("3. Exporter les indicateurs (JSON)", _cmd("exporter_dashboard_data.py")),
    ("4. Generer le tableau de bord", _cmd("generer_dashboard.py")),
    ("5. Publier vers docs/ (GitHub Pages)", "PUBLIER"),
]


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: "queue.Queue[str]" = queue.Queue()
        self.busy = False
        root.title("Mise a jour — Donnees sante DI-TSA")
        root.geometry("780x560")
        root.minsize(640, 460)

        haut = tk.Frame(root, padx=14, pady=12)
        haut.pack(fill="x")
        tk.Label(haut, text="Mise a jour des donnees et du tableau de bord",
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(haut, text=f"Depot : {RACINE}", fg="#5b6b82").pack(anchor="w")

        barre = tk.Frame(root, padx=14)
        barre.pack(fill="x")
        self.boutons = []
        for libelle, action in ETAPES:
            b = tk.Button(barre, text=libelle, anchor="w",
                          command=lambda a=action, l=libelle: self.lancer([(l, a)]))
            b.pack(fill="x", pady=2)
            self.boutons.append(b)

        actions = tk.Frame(root, padx=14, pady=8)
        actions.pack(fill="x")
        self.btn_tout = tk.Button(actions, text="  Tout faire (1 -> 5)  ",
                                  font=("Segoe UI", 11, "bold"),
                                  bg="#1d6fb8", fg="white",
                                  command=lambda: self.lancer(list(ETAPES)))
        self.btn_tout.pack(side="left")
        self.boutons.append(self.btn_tout)
        tk.Button(actions, text="Effacer le journal",
                  command=self.effacer).pack(side="left", padx=8)
        tk.Button(actions, text="Quitter", command=root.destroy).pack(side="right")

        self.etat = tk.Label(root, text="Pret.", anchor="w", fg="#155a97",
                             padx=14)
        self.etat.pack(fill="x")

        self.journal = scrolledtext.ScrolledText(root, height=18, wrap="word",
                                                 font=("Consolas", 9))
        self.journal.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.journal.configure(state="disabled")

        self.root.after(100, self._vider_queue)

    # -- journal ---------------------------------------------------------- #
    def log(self, texte: str):
        self.q.put(texte)

    def _vider_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__FIN__":
                    self._fin(item[1])
                    continue
                self.journal.configure(state="normal")
                self.journal.insert("end", item)
                self.journal.see("end")
                self.journal.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._vider_queue)

    def effacer(self):
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        self.journal.configure(state="disabled")

    # -- execution -------------------------------------------------------- #
    def _set_busy(self, busy: bool):
        self.busy = busy
        etat = "disabled" if busy else "normal"
        for b in self.boutons:
            b.configure(state=etat)

    def lancer(self, etapes: list):
        if self.busy:
            return
        self._set_busy(True)
        self.etat.configure(text="Traitement en cours...", fg="#b45309")
        threading.Thread(target=self._executer, args=(etapes,), daemon=True).start()

    def _executer(self, etapes: list):
        ok = True
        for libelle, action in etapes:
            self.log(f"\n===== {libelle} =====\n")
            try:
                if action == "PUBLIER":
                    code = self._publier()
                else:
                    code = self._run(action)
            except Exception as e:  # robustesse : on ne laisse jamais planter le GUI
                self.log(f"[ERREUR] {e}\n")
                code = 1
            if code != 0:
                ok = False
                self.log(f"[ECHEC] etape interrompue (code {code}).\n")
                break
            self.log("[OK]\n")
        self.q.put(("__FIN__", ok))

    def _run(self, cmd: list) -> int:
        self.log("$ " + " ".join(cmd) + "\n")
        proc = subprocess.Popen(cmd, cwd=str(RACINE), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
        for ligne in proc.stdout:
            self.log(ligne)
        proc.wait()
        return proc.returncode

    def _publier(self) -> int:
        if not DASH_SRC.exists():
            self.log(f"Introuvable : {DASH_SRC}\n")
            return 1
        DASH_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DASH_SRC, DASH_DST)
        self.log(f"Copie -> {DASH_DST}\n")
        return 0

    # -- fin -------------------------------------------------------------- #
    def _fin(self, ok: bool):
        self._set_busy(False)
        if ok:
            self.etat.configure(text="Termine avec succes.", fg="#15803d")
        else:
            self.etat.configure(text="Termine avec une erreur (voir journal).",
                                fg="#b91c1c")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
