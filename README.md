# Czarter Stillo 31 — Kalskie Nowiny

Robocza wersja serwisu Mazury.Holiday dla Radka. Po zalogowaniu można obejrzeć podstrony po polsku i angielsku, zdjęcia oraz sprawdzić wybór sprzętu i terminu. Kalendarz pracuje na danych pokazowych. Rezerwacje i płatności są wyłączone.

GitHub Pages publikuje katalog `docs/`. Dokumenty i zdjęcia podglądu są szyfrowane. Przeglądarka odszyfrowuje je po podaniu loginu i hasła. Wylogowanie jest dostępne w stopce.

W katalogu `wordpress/` znajduje się pełna paczka wtyczki w wersji 1.4.1. Aby uzyskać instalacyjny plik ZIP, rozpakuj zewnętrzne archiwum programem obsługującym ZIP AES-256 i podaj hasło podglądu.

## Aktualizacja podglądu

Rozpakuj wtyczkę z obu archiwów do `.work/mazury-holiday-stillo31/`. Z katalogu głównego repozytorium uruchom poniższe polecenia w środowisku z PHP CLI i Pythonem 3.10 lub nowszym.

```sh
python3 -m venv .work/venv
. .work/venv/bin/activate
python -m pip install -r tools/export/requirements.txt cryptography
python tools/export/build.py --source .work/mazury-holiday-stillo31 --output .work/public
python tools/gate/pack.py .work/public .work/publikacja --login admin
```

Ostatnie polecenie pyta o hasło i zapisuje wynik do pustego katalogu. Przy kolejnej publikacji zastąp katalog `docs/` zaszyfrowaną zawartością `.work/publikacja/`, łącznie z plikiem `.nojekyll`. Przy zmianie wtyczki uaktualnij również jej zaszyfrowaną paczkę w `wordpress/`.
