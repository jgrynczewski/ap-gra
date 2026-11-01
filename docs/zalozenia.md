# Gra przygodowa - pomysł i ustalenia

Gra tekstowa czytana na głos: scena (3-5 zdań) → 3-4 opcje do wyboru skanowaniem → kolejna scena. Ścieżki rozgałęziają się i zbiegają, kilka zakończeń - tak, żeby chciało się zagrać kilka razy.

**Stan (2026-11-01):** założenia fabularne i techniczne ustalone; zarys fabuły - [`fabula.md`](fabula.md), do akceptacji. Gra dla użytkowników AP (Assistive-Prototypes); front AP w tamtym repo.

## Gra 1 - prototyp: liceum z tajemnicą

Ustalenia:
- **Miejsce i gatunek:** liceum, ostatnia klasa, tajemnica do rozwiązania z przyjaciółmi; po drodze przyjaźń, zaufanie, może miłość.
- **Bohater:** chłopak, narracja w 2. osobie ("Wchodzisz do klasy..."). **Bez opisu ciała** - fabuła nie mówi, jak się porusza (nie każe biegać ani wspinać się, ale też nie mówi o wózku). Siła bohatera: spostrzegawczość, spryt, odwaga w rozmowie - i słowa (pisze teksty piosenek, patrz niżej).
- **Długość:** 20-30 min na rozgrywkę, ok. 15-20 wyborów, 6-8 zakończeń (ok. 80-120 scen).
- **Ton:** przygoda z humorem i dreszczykiem - nocne korytarze, sekrety, ktoś kłamie; ciepło między przyjaciółmi. Bez przemocy i śmierci; stawką prawda, przyjaźń, honor szkoły.
- **Zakończenia:** bez przegranej w trakcie - każda ścieżka dochodzi do pełnego zakończenia; zakończenia różnej jakości (triumf, słodko-gorzkie, "prawda wyszła na jaw, ale..."). Ponowna gra: sekrety tylko na niektórych ścieżkach, licznik odkrytych zakończeń.
- **Czasy:** lata 1999-2003 (stara matura, studniówka). Wieku bohatera nie podajemy - uczeń ostatniej klasy. **Bez gadżetów epoki** (telefony, discmany, Gadu-Gadu) - gracz ich nie używał; klimat dają ludzie, muzyka, szkoła.
- **Osobiste akcenty:** bohater pisze teksty piosenek - zagadki rozwiązywane słowami (ukryta wiadomość w tekście, właściwe słowo, piosenka, która na końcu coś zmienia).
- **Szyfr litera po literze - kluczowa zagadka:** w ważnym momencie bohater odczytuje ukrytą wiadomość sposobem znanym tylko jemu (jak tablica z literami, którą gracz pisał teksty) - jego przewaga nad innymi. Fabuła nie nazywa tego wprost.
- **Tajemnica:** miesiąc przed studniówką w szkole pojawiają się **anonimowe wiersze z ukrytymi wskazówkami**, prowadzące do starej szkolnej tajemnicy (zamknięta sala, zaginiona kronika, ktoś z dawnych lat). Bohater - autor tekstów - jako jedyny umie je czytać. Kto je pisze i po co? Kilka możliwych prawd zależnie od ścieżki.
- **Wątek miłosny - subtelny:** dziewczyna z klasy pomaga w śledztwie, a może wie więcej, niż mówi. Od wyborów zależy, czy coś się między nimi zacznie (np. wspólny taniec na studniówce w najlepszym zakończeniu). Niekonieczny do rozwiązania zagadki.
- **Postacie wymyślone** (bez prawdziwych osób) - obsada do zaproponowania i akceptacji.
- **Forma:** krótkie zdania (syntezator), opcje krótkie i wyraźnie różne, max 4; napięcie z tajemnicy, nie ze zręczności - bez limitów czasu.

Do zrobienia: zarys fabuły (obsada, możliwe prawdy, mapa ścieżek, zakończenia) do akceptacji, potem pisanie scen.

### Technologia (ustalenia 2026-11-01)

- **Osobne repo `ap-gra`** (to repo; `github.com/jgrynczewski/ap-gra`): silnik, API, scenariusz, narzędzia, nagrania, Dockerfile; później front przeglądarkowy. W AP tylko klient i moduł z planszą.
- **Silnik:** Python 3, czysta biblioteka (bez UI, z testami). Nad nim małe **HTTP API** (FastAPI) - `start`, `wybierz`; **bez sesji** - stan gry wraca do klienta razem ze sceną i jest odsyłany przy wyborze, więc ten sam serwer może działać lokalnie albo w chmurze.
- **Uruchomienie u użytkownika:** **kontener Docker** jak hub IoT (Python 3.12, FastAPI, port 8765) - gra na sąsiednim porcie (np. 8766), start razem z systemem. API serwuje też nagrania (i później grafiki).
- **Scenariusz:** czytelny plik tekstowy (sceny, opcje, warunki/zmienne stanu, zakończenia, pole na obraz sceny). Narzędzie sprawdzające: sceny nieosiągalne, opcje prowadzące donikąd, nieosiągalne zakończenia.
- **Głos:** nagrania generowane z góry Piperem (głos Gosia, `SYNTEZATOR.md`) dla każdej sceny i opcji - bez syntezy w trakcie gry, **bez mileny**. Znana długość nagrania → efekt pisania tekstu w takt czytania. Front przeglądarkowy później odtworzy te same pliki (Web Speech - ewentualnie).
- **Front AP** (Python 2.7, wx): klient `gra_client.py` (wzór: `iot_client.py`) + moduł z planszą; interakcja **identyczna jak w innych modułach AP** (np. Wicero): opcje podświetlane i czytane, dźwięki przy skanowaniu i wyborze, uśpienie po dwóch pustych przejściach, wybudzenie naciśnięciem. Tekst sceny wypisywany na ekranie w takt czytania (jak maszyna do pisania w starych grach); **skanowanie dopiero po skończeniu czytania**. Logika skanowania - do wydzielenia ze `modules/wicero.py` do wspólnej klasy (gra nie importuje modułu Wicero).
- **Zapis gry - po stronie klienta** (serwer niczego nie pamięta; restart kontenera nie gubi postępu). Front AP po każdym wyborze zapisuje `state` (scena + flagi) w pliku na komputerze gracza, np. `~/.ap-gra/zapis.json`. Po uruchomieniu gry, gdy jest zapis: plansza „Kontynuuj” / „Nowa gra”. W tym samym pliku odkryte zakończenia („odkryłeś 3 z 7”) - zostają po nowej grze. Zapis niepasujący do nowej wersji scenariusza (serwer zwraca 400 - np. nie ma sceny) → komunikat i gra od początku, bez zawieszenia. Front przeglądarkowy - to samo w pamięci przeglądarki.
- **Grafika / efekty:** później - w formacie od razu (pole na obraz / tło sceny).
- **Później:** front przeglądarkowy (JS) jako drugi klient tego samego API.

## Gra 2 - później: willa i klub muzyczny

Na podstawie prawdziwej historii gracza - **nie w prototypie, osobna gra**:
- Wielki dom (willa, ponad 100 pokoi, basen), w którym działał **klub muzyczny Atamay** - gracz był jego członkiem założycielem i pisał teksty piosenek. Do klubu należały też inne osoby z dzielnicy, również z dużymi ograniczeniami ruchowymi. W domu odbywały się bale i próby, zespół dał kilka publicznych koncertów.
- Teksty pisał z pomocą tablicy z literami: ktoś prowadził palcem po literach, a on dawał znak ruchem przy właściwej - litera po literze, zdanie po zdaniu.
- Pomysł na grę: przygoda z tajemnicą w willi (zamknięte skrzydła, zapomniane pokoje, basen nocą, strych) przy przygotowaniach do balu / koncertu; zespół to przyjaciele i podejrzani; finał - bal lub koncert.
- **Prowadzącej zespół nie przedstawiamy** (prawdziwa osoba, która zmarła w smutnych okolicznościach) - jeśli potrzebna taka postać, wymyślona, bez nawiązań.
