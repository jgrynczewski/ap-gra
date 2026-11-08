# HTTP API

Cienka warstwa nad silnikiem (`api/app.py` → `engine.Game`). Na komputerze z AP: kontener Docker obok huba IoT, `http://localhost:8766` (tylko z tego komputera). JSON w UTF-8.

**Bez sesji:** serwer nie pamięta stanu gry (zapisuje tylko log rozgrywek - niżej). Każdy widok zawiera `state` - klient trzyma go i odsyła bez zmian razem z wyborem. Dzięki temu ten sam serwer może działać lokalnie albo w chmurze, a klientów (AP, przeglądarka) może być wielu.

**Kilka gier:** każdy plik `scenariusz/*.md` to gra, jej identyfikator to nazwa pliku (`sala_pod_zegarem`, `ostatnia_zwrotka`). Trasy przyjmują `?game=<id>`; bez niego - gra domyślna (`sala_pod_zegarem`, zmienna `AP_GRA_DEFAULT`), więc starsi klienci działają bez zmian. Nieznana gra → 404. Stan (`state`) dotyczy jednej gry - klient trzyma osobny zapis dla każdej.

**Gry użytkownika** (z kreatora gier, [`kreator-gier.md`](kreator-gier.md)): `dane/gry/<id>/scenariusz.md`, nagrania w `dane/gry/<id>/audio/`. Serwer czyta katalog przy każdym zapytaniu, więc nowa gra jest dostępna bez restartu. Pomijane są: katalogi o nazwie spoza `[a-z0-9_]` (np. `<id>.tmp` w trakcie publikacji), katalogi bez scenariusza, scenariusze z błędem (ostrzeżenie w logu kontenera) i gry o identyfikatorze gry wbudowanej.

| Metoda i ścieżka | Wejście | Wyjście |
|---|---|---|
| `GET /v1/games` | - | `{"default", "games": [{"id", "title", "endings", "builtin", "title_audio", "kafelek", "animacja"}]}` - lista gier; `builtin` - gra wbudowana (`false` - gra użytkownika); `title_audio` - nagranie tytułu (czytane przy skanowaniu kafelka) albo `null`; `kafelek`, `animacja` - niżej |
| `GET /v1/health?game=` | - | `{"ok": true, "game", "title", "endings", "recordings", "interface"}` - czy serwer działa, tytuł gry, liczba zakończeń, liczba nagrań, przyciski planszy |
| `POST /v1/start` | - | widok pierwszej sceny |
| `POST /v1/choose` | `{"state": {...}, "option": 2}` | widok następnej sceny |
| `POST /v1/view` | `{"state": {...}}` | widok sceny z zapisu (kontynuacja gry); zapis niepasujący do scenariusza → 400 |
| `GET /v1/audio/<nazwa>.wav` | - | nagranie gry wbudowanej (adres z widoku) |
| `GET /v1/gry/<id>/audio/<nazwa>.wav` | - | nagranie gry użytkownika (adres z widoku) |
| `GET /v1/gry/<id>/kafelek.png` | - | obrazek na przycisk gry użytkownika |
| `GET /v1/gry/<id>/animacja/<nnnn>.png` | - | klatka animacji gry użytkownika (`0000.png`, `0001.png`, ...) |

**Kafelek i animacja** (gry użytkownika; wbudowane - `null`, AP rysuje je sam): `kafelek` - adres obrazka albo `null`; `animacja` - `{"fps", "klatki", "szerokosc", "wysokosc", "adres"}` albo `null`. Klatki: `adres` + `0000.png` ... (`klatki` - 1), w pętli, `fps` klatek na sekundę; jedna klatka = nieruchomy obrazek (animacja się nie udała). Kafelek = pierwsza klatka. Klient skaluje klatki do swojego panelu (proporcje ok. 1,08 : 1).

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
  "state": {"scene": "kuba_1", "flags": [], "rozgrywka": "3f9c0a1b2c3d"}
}
```

- `text` - tekst już dla stanu gracza (linie zależne od flag rozstrzygnięte); `\n\n` - nowy akapit, `\n` - nowy wers.
- `lines` - ten sam tekst w kawałkach do czytania: każda linia scenariusza osobno, z nagraniem. `before` - co przed nią: `""` (pierwsza), `" "` (ten sam akapit), `"\n"` (nowy wers), `"\n\n"` (nowy akapit); sklejenie `before + text` daje `text`.
- `audio` - `{"url", "duration"}` (sekundy) albo `null`, gdy nagrania nie ma (gra działa i bez nich). `duration` - do efektu pisania tekstu w takt czytania.
- **Odtwarzanie tekstu sceny:** linie po kolei; nagranie nie ma ciszy na końcu - klient robi przerwę: między liniami ok. 0,6 s (jak między zdaniami w nagraniu), przed nowym akapitem ok. 1 s.
- `options` - tylko widoczne; `number` podaje się w `/v1/choose`; `audio` - czytane, gdy skanowanie dojdzie do przycisku opcji (każda opcja to osobny przycisk).
- `ending` - przy zakończeniu `{"id", "title", "number", "total", "audio", "label", "label_audio"}`: `audio` - nagranie tytułu, `label` - "Zakończenie trzecie z siedmiu." (liczby słowami, żeby głos przeczytał je poprawnie) z nagraniem `label_audio`; `options` puste. Które zakończenia gracz już odkrył - zapisuje klient (na komputerze gracza).
- `state` - zapis gry: klient zapisuje go po każdym wyborze i może wrócić do gry po restarcie komputera (`docs/zalozenia.md` → "Zapis gry"). `rozgrywka` - identyfikator rozgrywki do logu (niżej); klient odsyła go bez zmian.
- `image` - na później (grafika sceny).

## Zapis rozgrywek

Serwer zapisuje każdą rozgrywkę każdej gry (wbudowanej i użytkownika) do `dane/rozgrywki/<id gry>.jsonl`, jedna linia na zdarzenie, z czasem (UTC):

- `start` - nowa gra od początku (nowy identyfikator `rozgrywka`);
- `kontynuacja` - powrót do zapisanej gry (`stary_zapis: true` - zapis sprzed logowania, dostaje nowy identyfikator);
- `wybor` - `scena`, numer i `tekst` opcji, `cel` (następna scena);
- `zakonczenie` - `zakonczenie` (identyfikator), `tytul`, `numer` z `wszystkich`.

Klient nic nie zmienia: identyfikator rozgrywki jest w `state`. Błąd zapisu logu nie przerywa gry (ostrzeżenie w logu kontenera).

Podsumowanie - ile rozgrywek, ile ukończonych, które zakończenia, ile razy i kiedy pierwszy raz (czas polski):

```bash
docker exec ap-gra python -m tools.statystyki                    # wszystkie gry
docker exec ap-gra python -m tools.statystyki sala_pod_zegarem   # jedna gra
docker exec ap-gra python -m tools.statystyki --json             # dane dla innych programów
```

## Przyciski planszy

Poza opcjami plansza ma stałe przyciski - też czytane głosem narratora. `GET /v1/health` → `"interface"`:

```json
{"powtorz": {"text": "Powtórz", "audio": {"url": "...", "duration": 0.8}},
 "wyjdz": {"text": "Wyjdź z gry", "audio": {...}},
 "kontynuuj": {"text": "Kontynuuj", "audio": {...}},
 "nowa_gra": {"text": "Nowa gra", "audio": {...}},
 "wybrales": {"text": "Wybrałeś:", "audio": {...}}}
```

`wybrales` - potwierdzenie po wyborze: klient czyta „Wybrałeś:”, potem nagranie wybranej opcji (wybrany przycisk podświetlony), dopiero potem następna scena.

Lista - `engine/voice.py` (`INTERFACE`); nowy przycisk = nowy wpis, nagranie powstaje przy budowaniu.

## Nagrania

- Generuje je `tools/nagraj.py` (Piper, głos i ustawienia w `engine/voice.py`) **w trakcie budowania obrazu** (`docker compose up -d --build`) - nie ma ich w repo. Piper i model głosu zostają w obrazie (`/app/models`, zmienna `AP_GRA_MODELS`), więc kreator gier nagrywa nowe gry w działającym kontenerze (`tools.nagraj.Narrator`), bez internetu.
- Nazwa nagrania = skrót z ustawień głosu i tekstu: niezmieniony tekst zachowuje nagranie, zmieniony dostaje nowe. Nagrania i model głosu (~60 MB, pobierany przy pierwszym budowaniu) leżą w pamięci podręcznej Dockera między budowaniami - po zmianie scenariusza nagrywa się tylko to, co nowe. Wymaga BuildKit (domyślnie od Dockera 23).
- Zmiana głosu lub ustawień w `engine/voice.py` → wszystko nagrywa się od nowa.

## Kreator gier (`ap-gra-kreator`, port 8767)

Osobna usługa z tego samego obrazu ([`kreator-gier.md`](kreator-gier.md)): jedyna z kluczem API (plik `.env`, wzór w `.env.example`). Każde zapytanie wraca od razu; AI pracuje w tle, a klient co sekundę pyta o stan rozmowy.

| Metoda i ścieżka | Wejście | Wyjście |
|---|---|---|
| `GET /v1/kreator/health` | - | `{"ok", "ai", "nagrania", "interface"}` - `ai`: czy jest klucz; `interface`: stałe przyciski planszy rozmowy z nagraniami |
| `POST /v1/kreator/rozmowy` | - | stan nowej rozmowy (zwykle `mysli`) |
| `GET /v1/kreator/rozmowy/<id>` | - | stan rozmowy |
| `POST /v1/kreator/rozmowy/<id>/odpowiedz` | `{"opcja": 2}` | stan (zwykle `mysli`) |
| `POST /v1/kreator/rozmowy/<id>/wroc` | - | poprzednie pytanie, bez pytania AI |
| `POST /v1/kreator/rozmowy/<id>/przerwij` | - | stan `przerwana` |
| `GET /v1/kreator/gry` | - | `{"gry": [...]}` - gry tworzone przez kreator (w toku, gotowe, nieudane) |
| `GET /v1/kreator/gry/<id>` | - | stan tworzenia jednej gry (`<id>` - identyfikator rozmowy) |
| `GET /v1/kreator/audio/<nazwa>.wav` | - | nagranie (adres ze stanu) |

Stan: `{"id", "status", "tekst", "audio", "opcje": [{"numer", "tekst", "audio"}], "mozna_wrocic", "pytanie_nr", "tytul"}`.

- `status`: `mysli` (AI pracuje - plansza mówi „Myślę...”, klient pyta ponownie), `pytanie` (pytanie AI; ostatnia opcja to zawsze „Inne propozycje”), `podsumowanie` (tytuł i streszczenie w `tekst`; opcje „Rozpocznij”, „Inny pomysł”), `blad` (AI zawiodło - WRÓĆ pokazuje ostatnie pytanie, żeby wybrać jeszcze raz), `przerwana`, `zatwierdzona` (wybrano „Rozpocznij” - gra zaczyna się tworzyć w tle).
- Odpowiedź lub WRÓĆ niepasujące do stanu → 409 `{"error"}`; nieznana rozmowa → 404.
- Nagrania pytania i opcji powstają, zanim pytanie zostanie pokazane (`audio: null`, gdy się nie udało - klient czyta własnym głosem).
- Historia: `dane/rozmowy/<id>/log.jsonl` - każde zapytanie do AI (całe), każda odpowiedź AI (z tokenami i identyfikatorem zapytania), każdy wybór, WRÓĆ, przerwanie i błąd; `stan.json` - bieżący stan. Rozmowy są w pamięci usługi: po restarcie kontenera klient zaczyna nową rozmowę (logi zostają).

### Tworzenie gry

„Rozpocznij” zleca stworzenie gry. Gry powstają w tle po kolei, jedna naraz: zarys → scenariusz (sprawdzany jak nasze gry, błędy wracają do AI) → kontrola fabuły → animacja (kod od AI uruchamia `ap-gra-rysownik` - bez sieci, z limitami; gdy się nie uda - nasz nieruchomy obrazek) → nagrania → publikacja. Wyniki kroków są w `dane/zadania/<id>/`, więc po wyłączeniu komputera praca rusza od kroku, na którym stanęła. Gotowa gra pojawia się w `dane/gry/g<id>/` i od razu na liście `GET /v1/games` (`builtin: false`).

Stan tworzenia: `{"id", "gra", "tytul", "status", "krok", "krok_nr", "krokow", "utworzona"}`.

- `status`: `w_toku`, `gotowa`, `nieudana`; `gra` - identyfikator gry w `/v1/games` (`g` + identyfikator rozmowy, `-` zamienione na `_`); `krok` - bieżący krok (`zarys`, `scenariusz`, `kontrola`, `animacja`, `nagrania`, `publikacja`), przy `nieudana` - krok, na którym się nie udało.
- Komunikaty głosowe (w `interface` z `/v1/kreator/health`): `tworze` - po „Rozpocznij”, `w_trakcie` - gra jeszcze się tworzy, `nieudana`; `wybrales` - „Wybrałeś:” jak w grze.
- Historia tworzenia (każde zapytanie do AI i odpowiedź, odrzucone scenariusze z błędami, kroki) trafia do tego samego logu co rozmowa: `dane/rozmowy/<id>/log.jsonl`; kopia w grze (`rozmowa.jsonl`).

## Uruchomienie

- **Kontener (komputer z AP):** `docker compose up -d --build` - startuje razem z systemem. Po zmianie scenariusza lub kodu: `git pull`, potem to samo polecenie.
- **Testy:** `docker build --target test .` - w tym samym obrazie co serwer (Python 3.12, te same pakiety) plus httpx i katalog `tests`; build przerywa się, gdy test nie przejdzie. Obraz serwera (`target: app` w `docker-compose.yml`) nie zawiera testów.
- Dokumentacja interaktywna: `http://localhost:8766/docs`.
- Inny katalog scenariuszy: `AP_GRA_SCENARIOS`; gra domyślna: `AP_GRA_DEFAULT`; inny katalog nagrań: `AP_GRA_AUDIO`; inny katalog danych (gry użytkownika): `AP_GRA_DATA` (domyślnie `dane/`).
- **Katalog `dane/`** obok repo (poza gitem) jest podpięty do kontenera (`docker-compose.yml`) - gry użytkownika, rozmowy i logi przetrwają przebudowanie obrazu. Pliki tworzone w kontenerze należą do roota.
