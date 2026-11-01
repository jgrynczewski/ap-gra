# HTTP API

Cienka warstwa nad silnikiem (`api/app.py` → `engine.Game`). Na komputerze z AP: kontener Docker obok huba IoT, `http://localhost:8766` (tylko z tego komputera). JSON w UTF-8.

**Bez sesji:** serwer niczego nie pamięta. Każdy widok zawiera `state` - klient trzyma go i odsyła bez zmian razem z wyborem. Dzięki temu ten sam serwer może działać lokalnie albo w chmurze, a klientów (AP, przeglądarka) może być wielu.

| Metoda i ścieżka | Wejście | Wyjście |
|---|---|---|
| `GET /v1/health` | - | `{"ok": true, "title", "endings"}` - czy serwer działa, tytuł gry, liczba zakończeń |
| `POST /v1/start` | - | widok pierwszej sceny |
| `POST /v1/choose` | `{"state": {...}, "option": 2}` | widok następnej sceny |

Błąd (nieznana scena, opcja spoza listy, gra skończona) → HTTP 400 `{"error": "..."}`; zły kształt zapytania → 422.

## Widok

```json
{
  "scene": "kuba_1",
  "text": "Kuba słucha z otwartymi ustami. ...\n\nWszyscy się odwracają. ...",
  "image": null,
  "options": [
    {"number": 1, "text": "Ucisz go, zanim powie więcej"},
    {"number": 2, "text": "Obróć wszystko w żart"}
  ],
  "ending": null,
  "state": {"scene": "kuba_1", "flags": []}
}
```

- `text` - tekst już dla stanu gracza (linie zależne od flag rozstrzygnięte); `\n\n` - nowy akapit, `\n` - nowy wers.
- `options` - tylko widoczne; `number` podaje się w `/v1/choose`.
- `ending` - przy zakończeniu `{"id", "title", "number", "total"}` (np. zakończenie 3 z 7), `options` puste. Które zakończenia gracz już odkrył - zapisuje klient (na komputerze gracza).
- `state` - zapis gry: klient zapisuje go po każdym wyborze i może wrócić do gry po restarcie komputera (`docs/zalozenia.md` → "Zapis gry").
- `image` - na później (grafika sceny).
- Planowane: adresy nagrań dla tekstu i opcji (nagrania generowane z góry Piperem).

## Uruchomienie

- **Kontener (komputer z AP):** `docker compose up -d --build` - startuje razem z systemem. Po zmianie scenariusza lub kodu: `git pull`, potem to samo polecenie.
- **Testy:** `docker build --target test .` - w tym samym obrazie co serwer (Python 3.12, te same pakiety) plus httpx i katalog `tests`; build przerywa się, gdy test nie przejdzie. Obraz serwera (`target: app` w `docker-compose.yml`) nie zawiera testów.
- Dokumentacja interaktywna: `http://localhost:8766/docs`.
- Inny scenariusz: zmienna `AP_GRA_SCENARIO` (ścieżka do pliku).
