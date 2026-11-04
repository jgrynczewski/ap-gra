# ap-gra

Gra przygodowa czytana na głos, dla użytkowników AP (Assistive-Prototypes): scena → 3-4 opcje wybierane skanowaniem → kolejna scena; rozgałęzienia, zbiegi ścieżek, kilka zakończeń. Pierwsza gra: **"Sala pod zegarem"** - liceum, 2003, tajemnica anonimowych wierszy. W AP: przycisk **„Tajemnica zegara”** na planszy gier (repo AP, `GRA_PLAN.md`).

**Stan (2026-11-01):** PoC kompletny - 27 scen, 7 zakończeń, 8-12 minut na rozgrywkę; ekran w AP przetestowany na komputerze użytkownika. Dalej: uwagi z grania, rozbudowa tylko, jeśli gra się spodoba.

- Mapa wszystkich repozytoriów (ap-gra, AP, Wicero), komputery, zasady pracy: `docs/mapa-projektow.md` w repo `wicero`
- Założenia (fabularne i techniczne): [`docs/zalozenia.md`](docs/zalozenia.md)
- Zarys fabuły: [`docs/fabula.md`](docs/fabula.md)
- Format scenariusza: [`docs/format.md`](docs/format.md)
- HTTP API: [`docs/api.md`](docs/api.md)

## Struktura

```
engine/              silnik (Python 3, bez UI): scenario.py - format, game.py - gra, check.py - sprawdzanie,
                     voice.py - głos narratora i nazwy nagrań
tools/nagraj.py      nagrania Piperem (w trakcie budowania obrazu Docker)
api/                 HTTP API (FastAPI) - cienka warstwa nad silnikiem, bez sesji
scenariusz/          scenariusze (*.md)
play.py              granie w terminalu - do pisania i testowania fabuły
tests/               testy silnika i API
docs/                założenia, fabuła, format, API
Dockerfile, docker-compose.yml   kontener na komputer z AP (port 8766, obok huba IoT)
```

Dalej (`docs/zalozenia.md` → "Technologia"): front w AP (moduł z planszą i skanowaniem), później front w przeglądarce.

## Użycie

Serwer i testy działają w kontenerze (Python 3.12, wersje pakietów z `requirements*.txt`) - na komputerze potrzebny tylko Docker. `play.py` i sprawdzanie scenariusza - zwykły Python 3, bez pakietów.

```bash
docker build --target test .                           # testy w kontenerze; build przerywa się przy błędzie
docker compose up -d --build                           # serwer gry: localhost:8766, start z systemem; dokumentacja: localhost:8766/docs
docker compose down                                    # zatrzymanie
python play.py scenariusz/sala_pod_zegarem.md          # zagraj w terminalu (numer opcji; r - od nowa, q - koniec)
python -m engine.check scenariusz/sala_pod_zegarem.md  # sprawdź scenariusz
```
