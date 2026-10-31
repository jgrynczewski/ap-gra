# ap-gra

Gra przygodowa czytana na głos, dla użytkowników AP (Assistive-Prototypes): scena → 3-4 opcje wybierane skanowaniem → kolejna scena; rozgałęzienia, zbiegi ścieżek, kilka zakończeń. Pierwsza gra: **"Sala pod zegarem"** - liceum, 2003, tajemnica anonimowych wierszy.

- Założenia (fabularne i techniczne): [`docs/zalozenia.md`](docs/zalozenia.md)
- Zarys fabuły: [`docs/fabula.md`](docs/fabula.md)
- Format scenariusza: [`docs/format.md`](docs/format.md)

## Struktura

```
engine/          silnik (Python 3, bez UI): scenario.py - format, game.py - gra, check.py - sprawdzanie
scenariusz/      scenariusze (*.md)
play.py          granie w terminalu - do pisania i testowania fabuły
tests/           testy silnika
docs/            założenia, fabuła, format
```

Plan (`docs/zalozenia.md` → "Technologia"): HTTP API (FastAPI) w kontenerze Docker obok huba IoT, nagrania Piperem generowane z góry, front w AP (moduł z planszą i skanowaniem), później front w przeglądarce.

## Użycie

Python 3.12+, bez dodatkowych pakietów (na razie).

```bash
python play.py scenariusz/sala_pod_zegarem.md        # zagraj (numer opcji; r - od nowa, q - koniec)
python -m engine.check scenariusz/sala_pod_zegarem.md  # sprawdź scenariusz
python -m unittest discover -s tests                   # testy
```
