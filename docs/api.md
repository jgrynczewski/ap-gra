# HTTP API

Cienka warstwa nad silnikiem (`api/app.py` → `engine.Game`). Na komputerze z AP: kontener Docker obok huba IoT, `http://localhost:8766` (tylko z tego komputera). JSON w UTF-8.

**Bez sesji:** serwer niczego nie pamięta. Każdy widok zawiera `state` - klient trzyma go i odsyła bez zmian razem z wyborem. Dzięki temu ten sam serwer może działać lokalnie albo w chmurze, a klientów (AP, przeglądarka) może być wielu.

| Metoda i ścieżka | Wejście | Wyjście |
|---|---|---|
| `GET /v1/health` | - | `{"ok": true, "title", "endings", "recordings"}` - czy serwer działa, tytuł gry, liczba zakończeń, liczba nagrań |
| `POST /v1/start` | - | widok pierwszej sceny |
| `POST /v1/choose` | `{"state": {...}, "option": 2}` | widok następnej sceny |
| `GET /v1/audio/<nazwa>.wav` | - | nagranie (adres z widoku) |

Błąd (nieznana scena, opcja spoza listy, gra skończona) → HTTP 400 `{"error": "..."}`; zły kształt zapytania → 422.

## Widok

```json
{
  "scene": "kuba_1",
  "text": "Kuba słucha z otwartymi ustami. ...\n\nWszyscy się odwracają. ...",
  "lines": [
    {"before": "", "text": "Kuba słucha z otwartymi ustami. ...",
     "audio": {"url": "/v1/audio/3f9c0a1b2c3d4e5f.wav", "duration": 6.84}},
    {"before": "\n\n", "text": "Wszyscy się odwracają. ...", "audio": {"url": "...", "duration": 5.1}}
  ],
  "image": null,
  "options": [
    {"number": 1, "text": "Ucisz go, zanim powie więcej", "audio": {"url": "...", "duration": 2.3}},
    {"number": 2, "text": "Obróć wszystko w żart", "audio": {"url": "...", "duration": 1.6}}
  ],
  "ending": null,
  "state": {"scene": "kuba_1", "flags": []}
}
```

- `text` - tekst już dla stanu gracza (linie zależne od flag rozstrzygnięte); `\n\n` - nowy akapit, `\n` - nowy wers.
- `lines` - ten sam tekst w kawałkach do czytania: każda linia scenariusza osobno, z nagraniem. `before` - co przed nią: `""` (pierwsza), `" "` (ten sam akapit), `"\n"` (nowy wers), `"\n\n"` (nowy akapit); sklejenie `before + text` daje `text`.
- `audio` - `{"url", "duration"}` (sekundy) albo `null`, gdy nagrania nie ma (gra działa i bez nich). `duration` - do efektu pisania tekstu w takt czytania.
- **Odtwarzanie:** linie po kolei; nagranie nie ma ciszy na końcu - klient robi przerwę: między liniami ok. 0,6 s (jak między zdaniami w nagraniu), przed nowym akapitem ok. 1 s.
- `options` - tylko widoczne; `number` podaje się w `/v1/choose`; `audio` - do czytania opcji przy skanowaniu.
- `ending` - przy zakończeniu `{"id", "title", "number", "total", "audio"}` (np. zakończenie 3 z 7; `audio` - nagranie tytułu), `options` puste. Które zakończenia gracz już odkrył - zapisuje klient (na komputerze gracza).
- `state` - zapis gry: klient zapisuje go po każdym wyborze i może wrócić do gry po restarcie komputera (`docs/zalozenia.md` → "Zapis gry").
- `image` - na później (grafika sceny).

## Nagrania

- Generuje je `tools/nagraj.py` (Piper, głos i ustawienia w `engine/voice.py`) **w trakcie budowania obrazu** (`docker compose up -d --build`) - nie ma ich w repo.
- Nazwa nagrania = skrót z ustawień głosu i tekstu: niezmieniony tekst zachowuje nagranie, zmieniony dostaje nowe. Nagrania i model głosu (~60 MB, pobierany przy pierwszym budowaniu) leżą w pamięci podręcznej Dockera między budowaniami - po zmianie scenariusza nagrywa się tylko to, co nowe. Wymaga BuildKit (domyślnie od Dockera 23).
- Zmiana głosu lub ustawień w `engine/voice.py` → wszystko nagrywa się od nowa.

## Uruchomienie

- **Kontener (komputer z AP):** `docker compose up -d --build` - startuje razem z systemem. Po zmianie scenariusza lub kodu: `git pull`, potem to samo polecenie.
- **Testy:** `docker build --target test .` - w tym samym obrazie co serwer (Python 3.12, te same pakiety) plus httpx i katalog `tests`; build przerywa się, gdy test nie przejdzie. Obraz serwera (`target: app` w `docker-compose.yml`) nie zawiera testów.
- Dokumentacja interaktywna: `http://localhost:8766/docs`.
- Inny scenariusz: zmienna `AP_GRA_SCENARIO` (ścieżka do pliku); inny katalog nagrań: `AP_GRA_AUDIO`.
