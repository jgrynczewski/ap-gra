# ap-gra

Gra przygodowa czytana na głos, dla użytkowników AP (Assistive-Prototypes): scena → 3-4 opcje wybierane skanowaniem → kolejna scena; rozgałęzienia, zbiegi ścieżek, kilka zakończeń. Pierwsza gra: **"Sala pod zegarem"** - liceum, 2003, tajemnica anonimowych wierszy.

- Założenia (fabularne i techniczne): [`docs/zalozenia.md`](docs/zalozenia.md)
- Zarys fabuły: [`docs/fabula.md`](docs/fabula.md)
- Format scenariusza: [`docs/format.md`](docs/format.md)
- HTTP API: [`docs/api.md`](docs/api.md)

## Struktura

```
engine/              silnik (Python 3, bez UI): scenario.py - format, game.py - gra, check.py - sprawdzanie
api/                 HTTP API (FastAPI) - cienka warstwa nad silnikiem, bez sesji
scenariusz/          scenariusze (*.md)
play.py              granie w terminalu - do pisania i testowania fabuły
tests/               testy silnika i API
docs/                założenia, fabuła, format, API
Dockerfile, docker-compose.yml   kontener na komputer z AP (port 8766, obok huba IoT)
```

Dalej (`docs/zalozenia.md` → "Technologia"): nagrania Piperem generowane z góry, front w AP (moduł z planszą i skanowaniem), później front w przeglądarce.

## Użycie

Python 3.12+. Silnik i `play.py` bez dodatkowych pakietów; API - `requirements.txt` (testy API - `requirements-dev.txt`).

```bash
python play.py scenariusz/sala_pod_zegarem.md        # zagraj (numer opcji; r - od nowa, q - koniec)
python -m engine.check scenariusz/sala_pod_zegarem.md  # sprawdź scenariusz
python -m unittest discover -s tests                   # testy (API pomijane bez fastapi)
uvicorn api.app:app --port 8766 --reload             # API lokalnie; dokumentacja: localhost:8766/docs
docker compose up -d --build                         # komputer z AP: kontener, start z systemem
```
