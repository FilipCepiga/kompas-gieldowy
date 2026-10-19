# Kompas Giełdowy

Prywatny skaner GPW i USA z portfelem treningowym (pieniądze na niby) i kalkulatorem oszczędzania.
Narzędzie edukacyjne, nie rekomendacja inwestycyjna.

- `index.html` – cała aplikacja (jeden plik).
- `fetch_data.py` – pobiera notowania dzienne z Yahoo Finance i zapisuje `data.json`.
- `.github/workflows/refresh.yml` – w dni robocze po zamknięciu GPW i giełd w USA odświeża dane i publikuje stronę na GitHub Pages.

Ręczne odświeżenie: zakładka Actions → „Odśwież notowania i opublikuj” → Run workflow.
