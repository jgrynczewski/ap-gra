# Jak podejrzeć, co się dzieje

Polecenia do wpisania w terminalu na komputerze z AP. Wszystkie tylko odczytują dane i niczego nie zmieniają.

## Czy wszystko działa

```
docker ps                                             # ap-gra, ap-gra-kreator, ap-gra-rysownik: "Up"
curl -s localhost:8766/v1/health | python3 -m json.tool          # serwer gry
curl -s localhost:8767/v1/kreator/health | python3 -m json.tool  # kreator; "ai": true = klucz API jest ustawiony
```

## Rozmowa z AI i tworzenie gry

Cała historia jednej rozmowy i tworzonej z niej gry jest w jednym pliku: `~/ap-gra/dane/rozmowy/<id>/log.jsonl`. Najpierw ustaw ostatnio zapisywany log (raz w danym oknie terminala):

```
LOG="$(ls -t ~/ap-gra/dane/rozmowy/*/log.jsonl | head -1)"
```

Co się dzieje teraz, na żywo (`Ctrl+C` kończy podgląd, tworzenia gry nie przerywa):

```
tail -n 50 -f "$LOG" | grep --line-buffered -oE '^\{"czas": "[^"]*", "rodzaj": "[^"]*"(, "(krok|cel)": "[^"]*")?'
```

Czas jest w UTC (w Polsce zimą +1 godzina, latem +2).

| Wpis | Znaczenie |
|---|---|
| `start` | początek rozmowy |
| `pokazane` | AP pokazał pytanie albo streszczenie |
| `odpowiedz_uzytkownika` | co wybrał użytkownik |
| `odpowiedz_ai_odrzucona` | odpowiedź AI nie przeszła kontroli, będzie kolejna próba |
| `krok_start`, `krok_koniec` | początek i koniec etapu tworzenia: zarys, scenariusz, kontrola, animacja, nagrania, publikacja |
| `ai_zapytanie` | AI pracuje; przy scenariuszu długo może nie być nowej linii i to normalne |
| `ai_odpowiedz` | AI skończyło odpowiadać |
| `ai_blad`, `blad` | błąd: pełny opis jest w tej linii logu |
| `scenariusz_odrzucony`, `animacja_odrzucona` | wynik nie przeszedł kontroli, będzie kolejna próba |
| `kontrola_pominieta` | kontrola fabuły się nie udała, zostaje scenariusz sprawdzony programem |
| `animacja_zapasowa` | animacja się nie udała, gra dostaje nieruchomy obrazek |
| `blad_nagrania` | nie powstało nagranie, AP przeczyta tekst swoim głosem |
| `tworzenie_gotowe`, `tworzenie_nieudane` | koniec tworzenia |

Przebieg rozmowy (pytania i wybory użytkownika):

```
grep -E '"rodzaj": "(pokazane|odpowiedz_uzytkownika)"' "$LOG" | cut -c1-400
```

Zużycie tokenów przy każdym zapytaniu do AI:

```
grep '"rodzaj": "ai_odpowiedz"' "$LOG" | grep -oE '"cel": "[^"]*"|"tokeny": \{[^}]*\}'
```

Krótki stan wszystkich tworzonych i stworzonych gier (status, krok):

```
curl -s localhost:8767/v1/kreator/gry | python3 -m json.tool
```

## Pliki gry

```
ls ~/ap-gra/dane/zadania/                   # gry w trakcie tworzenia i wyniki kolejnych etapów
ls ~/ap-gra/dane/gry/                       # gry gotowe
less ~/ap-gra/dane/gry/<gra>/scenariusz.md  # scenariusz
less ~/ap-gra/dane/gry/<gra>/rysunek.py     # kod animacji napisany przez AI
```

## Usługi

```
docker logs --tail 30 ap-gra-kreator        # dopisz -f, żeby oglądać na żywo
docker logs --tail 30 ap-gra-rysownik       # rysowanie animacji
docker logs --tail 30 ap-gra                # serwer gry
```

## AP

Błędy po stronie AP (gra, rozmowa, plansza GRY PRZYGODOWE) są w pliku `gra.log` w katalogu AP:

```
tail -n 30 ~/Assistive-Prototypes/gra.log
```

Który proces to AP (do `top -p <PID>`): wiersz z `ap.py`, a nie z `uvicorn` ani `rysownik`:

```
ps -eo pid,args | grep '[p]ython' | cut -c1-110
```

## Rozgrywki

Ile razy grano, które zakończenia odkryto, kiedy i ile razy (czas polski):

```
docker exec ap-gra python -m tools.statystyki                    # wszystkie gry
docker exec ap-gra python -m tools.statystyki sala_pod_zegarem   # jedna gra
```

Pełna historia wyborów z datami: `~/ap-gra/dane/rozgrywki/<gra>.jsonl`.

## Kredyty i subskrypcja

Kreator korzysta z klucza API, czyli z kredytów. Subskrypcja rozlicza się osobno i kreatora nie dotyczy.

**Kredyty API (kreator gier), Claude Console:**
- Stan kredytów i limit wydatków: https://platform.claude.com/settings/billing
- Zużycie (wykresy tokenów, filtr po kluczu `ap-gra`): https://platform.claude.com/usage
- Limity zapytań na minutę: https://platform.claude.com/usage/limits

**Subskrypcja (Claude w przeglądarce i Claude Code):**
- Limity sesji i tygodniowe: https://claude.ai/settings/usage
- W Claude Code: polecenie `/status`
