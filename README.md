# ap-gra

Gra przygodowa czytana na głos, dla użytkowników AP (Assistive-Prototypes): scena → 3-4 opcje wybierane skanowaniem → kolejna scena; rozgałęzienia, zbiegi ścieżek, kilka zakończeń. Gry (jeden serwer, każda w `scenariusz/<id>.md`):
- **"Sala pod zegarem"** (`sala_pod_zegarem`) - liceum, 2003, tajemnica anonimowych wierszy. W AP: przycisk **„Tajemnica zegara”** na planszy gier. PoC kompletny (2026-11-01): 27 scen, 7 zakończeń, 8-12 minut; przetestowany w AP.
- **"Ostatnia zwrotka"** (`ostatnia_zwrotka`, 2026-11-04) - romans: willa z klubem muzycznym, nowa wokalistka Nina wyjeżdża po lecie; gracz pisze dla niej piosenkę (wybiera wersy). 23 sceny, 9 zakończeń (3 wygrane, 3 neutralne, 3 przegrane), 8-12 minut. W AP: osobny przycisk na planszy gier. Zarys: [`docs/fabula-ostatnia-zwrotka.md`](docs/fabula-ostatnia-zwrotka.md).

Repo AP: `GRA_PLAN.md` (instalacja serwera, testy).

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
