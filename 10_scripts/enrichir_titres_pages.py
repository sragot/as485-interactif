#!/usr/bin/env python3
"""Phase 4 — Enrichir le gabarit de codes avec les titres de page officiels (MSSS)."""
from __future__ import annotations
import argparse, re
import pandas as pd
import pdfplumber

PAGE_RE = re.compile(r"Page\s+([0-9]{1,2}[A-Z]?)\s*\(GESTRED", re.IGNORECASE)
EXCLURE = ("ETABLISSEMENT", "GESTRED", "REGION", "ANNEE", "NOM DE")


def _sansacc(s: str) -> str:
    return (s.upper().replace("É", "E").replace("È", "E").replace("Ê", "E")
            .replace("À", "A").replace("Ô", "O").replace("Î", "I").replace("Ç", "C"))


def titres_depuis_pdf(pdf_path: str) -> dict:
    titres: dict = {}
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            lines = [l.strip() for l in (pg.extract_text() or "").split("\n") if l.strip()]
            code = None
            for l in lines:
                m = PAGE_RE.search(l)
                if m:
                    code = m.group(1).upper()
                    break
            if not code:
                continue
            for l in lines:
                lettres = [c for c in l if c.isalpha()]
                if len(lettres) < 12:
                    continue
                if sum(c.isupper() for c in lettres) / len(lettres) < 0.85:
                    continue
                if any(x in _sansacc(l) for x in EXCLURE):
                    continue
                titres.setdefault(code, re.sub(r"\s+", " ", l).strip())
                break
    return titres


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dico", required=True)
    ap.add_argument("--formulaire", required=True)
    ap.add_argument("--pdf", required=True)
    args = ap.parse_args()

    titres = titres_depuis_pdf(args.pdf)
    print(f"{len(titres)} titres de page extraits pour {args.formulaire} :")
    for k in sorted(titres):
        print(f"  Page {k:<4} {titres[k][:80]}")

    d = pd.read_csv(args.dico, dtype={"page": "string"})
    mask = d["formulaire"] == args.formulaire
    lut = {}
    for k, v in titres.items():
        for variant in (k, k.zfill(2), (k.lstrip("0") or "0")):
            lut[variant] = v
    key = d.loc[mask, "page"].astype("string").str.upper()
    d.loc[mask, "page_titre"] = key.map(lut).values

    n = int(d.loc[mask, "page_titre"].notna().sum())
    tot = int(mask.sum())
    d.to_csv(args.dico, index=False, encoding="utf-8")
    print(f"\npage_titre rempli pour {n}/{tot} codes {args.formulaire}.")
    sans = d.loc[mask & d["page_titre"].isna(), "page"].dropna().unique()
    if len(sans):
        print("Pages sans titre :", sorted(map(str, sans)))


if __name__ == "__main__":
    main()
