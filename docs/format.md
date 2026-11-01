# Format scenariusza

Scenariusz to plik tekstowy w stylu Markdown (`scenariusz/*.md`) - czyta się jak tekst książki, minimum znaków technicznych. Parser: `engine/scenario.py`, sprawdzanie: `python -m engine.check scenariusz/sala_pod_zegarem.md`.

## Przykład

```
# Sala pod zegarem

## kronika_1
Biblioteka pachnie kurzem.
Maciek kartkuje kronikę z 1983 roku.

"Zespół Echo" - mówi. - "Nigdy o nich nie słyszałem."

> ustaw: kronika

* Zapytaj o zdjęcie z auli -> kronika_zdjecie
* Zabierz kronikę do pani Wandy -> wanda_1
* [klucz] Idź od razu do auli -> aula_wejscie
* [!kuba_wie] Powiedz o wszystkim Kubie -> kuba_1
```

## Zasady

| Element | Zapis | Znaczenie |
|---|---|---|
| Tytuł gry | `# Tytuł` | pierwsza linia pliku |
| Scena | `## identyfikator` | małe litery, cyfry, `_`; **pierwsza scena w pliku = start gry** |
| Tekst sceny | zwykłe linie pod nagłówkiem | linie łączone w akapit; pusta linia = nowy akapit. 3-5 krótkich zdań (czyta syntezator) |
| Wers (wiersz, piosenka) | `\| tekst wersu` | linia zostaje osobną linią (nie łączy się w akapit) - wiersze, akrostychy, teksty piosenek |
| Linia zależna od flag | `[flaga] tekst`, `[!flaga] tekst` | linia pokazana (i czytana) tylko przy spełnionym warunku - **reakcja na wcześniejszy wybór na początku sceny**, zamiast osobnej sceny-przystanku |
| Opcja | `* tekst -> cel` | wybór gracza; `cel` - identyfikator sceny. **Max 4 opcje** widoczne naraz |
| Warunek opcji | `* [flaga] ...`, `* [!flaga] ...`, `* [a, !b] ...` | opcja widoczna, gdy flaga jest ustawiona (`!` - gdy nie jest); kilka warunków - wszystkie naraz |
| Skutek opcji | `* tekst -> cel +flaga -inna` | wybór ustawia (`+`) / kasuje (`-`) flagi - różne opcje mogą prowadzić do tej samej sceny, a i tak zostawić ślad |
| Ustawienie flagi | `> ustaw: a, b` | przy wejściu do sceny (przed pokazaniem opcji) |
| Skasowanie flagi | `> usun: a` | jw. |
| Zakończenie | `> koniec: Tytuł zakończenia` | scena kończy grę - bez opcji |
| Obraz | `> obraz: plik.png` | na później (grafika sceny) |
| Komentarz | `// ...` | pomijany - notatki autora |

- Kolejność w scenie: tekst, potem dyrektywy `>` i opcje (tekstu po opcjach nie ma).
- Flagi to zmienne "tak/nie" (np. `kuba_wie`, `klucz`) - zapamiętują, co gracz zrobił, żeby później pokazać inne opcje. Na starcie żadna nie jest ustawiona.
- Każda scena poza zakończeniami musi mieć opcje; w każdej sytuacji gracz musi mieć co najmniej jedną widoczną opcję - pilnuje tego sprawdzanie.
- **Wybór ma coś zmieniać** - kierunek, flagę albo relację z postacią. Scena z jedną opcją ("Dalej") kosztuje gracza naciśnięcie i nic nie daje: tylko gdy potrzebna pauza (np. przed zwrotem akcji), rzadko i nigdy dwie pod rząd. Reakcję na wybór pisz na początku następnej sceny (`[flaga] ...`).
- Kolejność zmian flag: skutek opcji (`+` / `-`), potem `> ustaw` / `> usun` sceny docelowej.

## Sprawdzanie (`engine/check.py`)

Przechodzi wszystkie możliwe rozgrywki (sceny razem z flagami) i zgłasza:
- **błędy:** opcja prowadzi do nieistniejącej sceny; scena bez opcji, która nie jest zakończeniem; sytuacja, w której żadna opcja nie jest widoczna (gracz utknął); więcej niż 4 widoczne opcje naraz; scena lub zakończenie, do którego nie da się dojść; **tekst sceny za długi na ekran**;
- **uwagi:** flaga sprawdzana, ale nigdzie nie ustawiana (lub odwrotnie); powtórzony tekst opcji w scenie; dwie sceny z jedną opcją pod rząd.

Na koniec statystyki: liczba scen, zakończeń, najdłuższy tekst, najkrótsza i najdłuższa rozgrywka (w wyborach).

**Błąd = obraz się nie zbuduje** (`docker compose up -d --build` sprawdza scenariusz przed nagrywaniem).

## Długość tekstu sceny

Gracz nie przewija - cały tekst sceny musi zmieścić się na ekranie gry w AP (obok scenki z zegarem, nad 4 opcjami). Limit (`engine/screen.py`): **10 linii ekranu po ok. 55 znaków**. Liczy się:
- akapit - tyle linii, na ile zawinie się po 55 znaków; wers (`| `) - osobno, każdy od nowej linii;
- przerwa między akapitami - pół linii;
- zakończenie - dodatkowo 3,5 linii (tytuł, „Zakończenie … z …”, odkryte zakończenia);
- linie warunkowe - liczy się najdłuższy wariant, jaki gracz może zobaczyć.

Przykład na granicy limitu - scena `start`: akapit (2 linie) + wiersz (5 wersów) + akapit (2 linie) + 2 przerwy = 10. Gdyby tekst jednak się nie zmieścił (inna rozdzielczość ekranu), AP lekko zmniejszy czcionkę.
