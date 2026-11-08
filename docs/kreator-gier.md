# Tworzenie gier przez użytkownika AP

**Status:** projekt zatwierdzony 2026-11-07, budowa w toku (plan niżej). Użytkownik AP odpowiada na pytania na planszy ze skanowaniem, a gotowa gra pojawia się jako nowy kafelek, bez udziału programisty.

## Ustalenia

- **Bez agenta z dostępem do kodu.** Stały ciąg kroków z AI w środku: opis → zarys → scenariusz → `check.py` → poprawki → kontrola fabuły → animacja → kafelek → nagrania → publikacja. Niepowodzenie oznacza brak kafelka, a nie zepsuty AP.
- **Historia rozmowy z AI zawsze zapisana** (decyzja 2026-11-07): każde zapytanie do AI, każda odpowiedź AI i każda odpowiedź użytkownika (także WRÓĆ i przerwanie) trafia do logu. Wszystkie wywołania AI przechodzą przez jedną funkcję, która zapisuje log przed wysłaniem i po odebraniu, więc nie da się wywołać AI bez zapisu.
- **Gra to paczka danych w katalogu** (scenariusz, opis, klatki animacji, kafelek, nagrania). Dodanie gry nie wymaga zmiany kodu.
- **Gra zostaje lokalnie** na komputerze użytkownika (decyzja 2026-11-07). Format paczki ma pozwalać na późniejsze przenoszenie gier.
- **Tworzenie działa w `ap-gra`**, który już działa w Dockerze na komputerze z AP. Internet jest potrzebny tylko do stworzenia gry; granie działa bez niego.
- **AP nie czeka na AI.** Zleca pracę i wraca do innych zajęć, a gotowa gra pojawia się jako kafelek. `gra_client` ma limit 10 s, po którym mówi „Gra nie jest uruchomiona”.
- **Rozmowa z AI od pierwszego pytania**, z przyciskiem WRÓĆ. AP pokazuje każde pytanie po otrzymaniu odpowiedzi od AI i nie zacina się w tym czasie.
- **Na start tylko wybór z opcji**, w tym „INNE PROPOZYCJE” (decyzja 2026-11-07).
- **Nowa plansza GRY PRZYGODOWE** (decyzja 2026-11-07): w `new_games.py` jeden nowy kafelek zamiast Tajemnicy i Zwrotki, które przechodzą na nową planszę. Plansza jest budowana z listy gier, ma strony i przycisk NOWA GRA.
- **Grafika rysowana prostymi kształtami**, na poziomie ogrodu z „Ostatniej zwrotki”; bez modelu graficznego (decyzja 2026-11-07).
- **Animacja osobna dla każdej gry**, pisana przez AI jako kod rysujący, jak `NightScene`. Kod działa tylko w kontenerze bez sieci, z limitem czasu, i zapisuje klatki do plików. AP tylko je odtwarza, więc błąd w kodzie nie wywróci AP. Sprawdzić płynność i zużycie pamięci na laptopie z AP.
- **Kafelek: pierwsza klatka animacji.** Gdy animacja się nie uda - gotowy obrazek zamiast przerywania tworzenia gry.
- **Na start jeden komputer** (decyzja 2026-11-07). Klucz API w ustawieniach `ap-gra` na tym komputerze. Przy kilku osobach potrzebne pośrednictwo w chmurze z limitem na osobę, bo klucz nie powinien być na cudzych komputerach.

## Ustawienia domyślne (2026-11-07)

- Długość gry jak nasze dwie: 8-12 minut, 20-30 scen, kilka zakończeń.
- Rozmowa: ok. 5-8 pytań, potem AI streszcza pomysł, a użytkownik wybiera ROZPOCZNIJ albo INNY POMYSŁ.
- W grach nie występują prawdziwe osoby.
- Limit kosztów ustawiony na koncie API.
- Nieudane tworzenie: kilka automatycznych prób, potem głosowy komunikat, że gry nie udało się stworzyć; kafelek się nie pojawia.

## Architektura (decyzja 2026-11-07)

- **Trzy usługi w `docker-compose.yml`, jeden obraz:** `ap-gra` (granie, jak dziś, bez internetu i bez klucza), `ap-gra-kreator` (rozmowa i tworzenie gier, jedyna z internetem i kluczem API), `ap-gra-rysownik` (uruchamia kod animacji napisany przez AI, `network_mode: none`, limit pamięci i CPU).
- **Wspólny katalog danych** `dane/` (obok repo, poza gitem): `gry/<id>/` (scenariusz, `gra.json`, klatki, kafelek, nagrania), `rozmowy/<id>/` (log rozmowy), `zadania/<id>/` (wyniki kolejnych kroków tworzenia). Wbudowane gry zostają w obrazie, gry użytkownika w `dane/`. API czyta listę gier przy każdym zapytaniu, nie tylko przy starcie.
- **AP rozmawia tylko z naszymi usługami na tym komputerze** (`ap-gra` do grania, `ap-gra-kreator` do tworzenia); z AI łączy się wyłącznie kreator (Python 2.7 w AP nie łączy się z AI). Odpowiedź wysłana do kreatora wraca od razu, a AP co sekundę w tle pyta o następne pytanie. Mieści się to w limicie 10 s, a plansza mówi „Myślę...”.
- **Odpowiedź AI w stałym formacie JSON** (pytanie, do 4 opcji, czy koniec, streszczenie), sprawdzanym przez kod, w tym długość tekstu na ekranie. WRÓĆ nie pyta AI ponownie: usuwa ostatnią parę z rozmowy i pokazuje zapisane wcześniej pytanie.
- **Tworzenie jako kolejka kroków:** każdy krok zapisuje wynik do `zadania/<id>/`, więc po wyłączeniu komputera praca rusza od ostatniego kroku. Błędy `check.py` wracają do AI, najwyżej 3 razy.
- **Nagrania:** Piper w obrazie uruchomieniowym (dziś jest tylko w etapie budowania), pytania nagrywane na bieżąco, gra po napisaniu przez `tools/nagraj.py`. Gdy Piper zawiedzie, AP czyta syntezatorem.
- **Publikacja:** gra składana w `gry/<id>.tmp` i przemianowana jednym ruchem na `gry/<id>`, więc AP nigdy nie widzi połowy gry.
- **Log:** `rozmowy/<id>/log.jsonl`, jedna linia na zdarzenie (czas, rodzaj, treść), z pełnym zapytaniem i odpowiedzią AI oraz zużyciem tokenów. Kopia rozmowy trafia też do paczki gry. Logi nie są usuwane automatycznie.

## Plan

Testy automatyczne w kontenerze (`docker build --target test .`) po każdym etapie; AI w testach zastąpione udawanymi odpowiedziami, więc testy nie kosztują i nie potrzebują internetu.

**Etap 1 - gry z katalogu `dane/` (`ap-gra`)**
- [x] API czyta gry użytkownika z `dane/gry/<id>/` przy każdym zapytaniu; nagrania gry w `dane/gry/<id>/audio/` (2026-11-07)
- [x] Uszkodzona gra lub katalog `.tmp` jest pomijany, a reszta działa
- [x] `docker-compose.yml`: katalog `dane/` podpięty do kontenera; `dane/` poza gitem
- [x] Testy (39 OK w kontenerze); `docs/api.md`

**Etap 2 - nagrywanie w działającym kontenerze**
- [x] Piper i model głosu w obrazie uruchomieniowym (`/app/models`); nagrywanie jako funkcja do wywołania z kodu: `tools.nagraj.Narrator` - `recording(tekst)` i `record_all(teksty, katalog)` (2026-11-08)
- [x] Testy z prawdziwym głosem w obrazie testowym (41 OK). Krótkie pytanie: ok. 1-2 s nagrania plus ok. 2 s na wczytanie modelu przy pierwszym nagraniu (na komputerze z Windows; na laptopie z AP sprawdzić w testach funkcjonalnych)
- Obraz urósł z ok. 300 MB do ok. 700 MB (biblioteki Pipera i model). Gdyby brakowało miejsca na dysku - osobny, lżejszy obraz do samego grania

**Etap 3 - rozmowa (`ap-gra-kreator`)**
- [x] Jedna funkcja wywołania AI z zapisem do logu (`kreator/ai.py`); klucz z pliku `.env` poza repo (wzór `.env.example`) (2026-11-08)
- [x] Trasy rozmowy: start, odpowiedź, WRÓĆ, przerwij, stan (pytanie albo „myślę”) - `kreator/app.py`, port 8767, opis w `docs/api.md`
- [x] Sprawdzanie formatu (schemat JSON) i długości odpowiedzi AI; zła odpowiedź wraca do AI z opisem błędu, najwyżej 3 próby, potem stan `blad`
- [x] Streszczenie pomysłu, ROZPOCZNIJ / INNY POMYSŁ; „Inne propozycje” dodawane przez kod; nagrania pytań przed pokazaniem
- [x] Testy z udawanym AI (58 OK)
- Model `claude-opus-5-5`, wysiłek `medium` (zmiana w `.env`). Przy odmowie z powodów bezpieczeństwa API samo ponawia na innym modelu (`fallbacks: "default"`)
- Prompt rozmowy: `kreator/prompty/rozmowa.md`
- Do sprawdzenia w etapie 7: pierwsze prawdziwe zapytanie do AI (format zapytania sprawdzony tylko na udawanym AI); `docker compose` na komputerze z AP w wersji co najmniej 2.24 (opcjonalny `.env`)

**Etap 4 - tworzenie gry**
- [x] Kolejka kroków z zapisem wyników i wznowieniem po restarcie (`kreator/tworzenie.py`, 2026-11-08): ROZPOCZNIJ zleca grę; gry powstają po kolei, jedna naraz
- [x] Zarys, scenariusz, `check.py` z poprawkami (najwyżej 3), kontrola fabuły
- [x] Nagrania gry, publikacja przez `.tmp` i przemianowanie
- [x] Stan tworzenia do odczytu przez AP (w toku / gotowa / nieudana) - `GET /v1/kreator/gry`, opis w `docs/api.md`
- [x] Testy z udawanym AI (73 OK)
- Kroki: zarys → scenariusz → kontrola → nagrania → publikacja (animacja i kafelek dojdą w etapie 5, przed publikacją). Wyniki w `dane/zadania/<id>/` (ten sam identyfikator co rozmowa), gra w `dane/gry/g<id>/` (`scenariusz.md`, `gra.json`, `audio/`, `rozmowa.jsonl` - kopia logu)
- Wymagania dla scenariusza z AI (jak nasze gry): 18-32 sceny, 3-9 zakończeń, najkrótsza rozgrywka co najmniej 5 wyborów, opcja do 60 znaków, tytuł z pomysłu, plus wszystkie błędy `check.py`
- Kontrola fabuły: AI czyta scenariusz i zgłasza najwyżej 5 poważnych problemów; scenariusz wraca raz do poprawki. Gdy poprawka się nie uda albo kontrola zawiedzie - zostaje scenariusz sprawdzony programem (gra i tak powstaje)
- Nieudane nagrania nie przerywają tworzenia: AP przeczyta grę swoim głosem
- Pisanie gry: wysiłek AI `high` (`AP_GRA_EFFORT_GRA` w `.env`), odpowiedzi do 64 000 tokenów, odbierane w kawałkach (streaming), bo scenariusz to długi tekst
- Prompty: `kreator/prompty/zarys.md`, `scenariusz.md`, `kontrola.md`
- Do sprawdzenia w etapie 7: ile trwa stworzenie gry i ile kosztuje (zużycie tokenów jest w logu)

**Etap 5 - animacja (`ap-gra-rysownik`)**
- [ ] Kontener bez sieci, z limitem pamięci, CPU i czasu
- [ ] AI pisze kod rysujący; klatki do plików, sprawdzenie, że nie są puste; pierwsza klatka jako kafelek; gotowy obrazek zapasowy
- [ ] Trasy API do klatek i kafelka

**Etap 6 - AP**
- [ ] `new_games.py`: kafelek GRY PRZYGODOWE zamiast Tajemnicy i Zwrotki
- [ ] Plansza GRY PRZYGODOWE z listy gier: kafelki, strony (DALEJ), NOWA GRA, POWRÓT
- [ ] Plansza rozmowy: pytanie, opcje, WRÓĆ, PRZERWIJ, „Myślę...”
- [ ] Odtwarzanie animacji w planszy gry
- [ ] Gra w trakcie tworzenia i nieudana - komunikat głosowy

**Etap 7 - uruchomienie (Ty)**
- [ ] Klucz API i limit kosztów na koncie
- [ ] `.env` z kluczem na komputerze z AP, `docker compose up -d --build`
- [ ] Testy funkcjonalne na komputerze z AP: stworzenie gry od początku do końca, WRÓĆ, przerwanie, 21. gra (strony), płynność animacji

## Główna niewiadoma

Jakość gry napisanej bez poprawek człowieka. Bez osobnej próby przed kodem: sprawdzimy ją w testach funkcjonalnych na komputerze z AP, gdy całość będzie działać (decyzja 2026-11-07).

## TODO

- [ ] Wpisywanie własnego tekstu podczas tworzenia gry (PISAK) - po pierwszej wersji; pisanie skanowaniem jest powolne, dlatego nie na start
- [ ] Poprawki po zagraniu: przycisk POPRAW, nowa wersja gry (zapis stanu przestaje do niej pasować), limit np. 3 na grę - po pierwszej wersji. To pierwsza interakcja użytkownika AP z AI, więc na start jak najmniej naraz (decyzja 2026-11-07)
- [ ] Usuwanie gier użytkownika - na razie ręcznie z `dane/gry/`
