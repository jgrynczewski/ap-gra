# Kompan: rozmowa z AI w AP

**Status:** projekt zatwierdzony 2026-11-08, kod jeszcze nie powstał (następny krok: etap 1). Testy ręczne: `KOMPAN_PLAN.md` w repo AP. Kompan to rozmówca dla użytkownika AP: rozmawia na dowolny temat, z czasem coraz lepiej go zna, może dowiedzieć się czegoś na prośbę innej osoby i przekazać to, co ważne, za zgodą użytkownika.

Pomysł pochodzi z repozytorium `kompan` (gałąź `feat/user-context-system`), a technologia z kreatora gier (`kreator-gier.md`), który działa dobrze. Kodu starego Kompana nie używamy.

## Ustalenia

### Rozmowa

- Kompan zadaje jedno pytanie naraz. Pod nim są 2-4 odpowiedzi od AI oraz **Blisko** (AI dopytuje, co było trafne), **Inne propozycje** i **Zmień temat**, a na dole **WRÓĆ** i **ZAKOŃCZ**
- **Pyta tylko wtedy, gdy odpowiedź coś zmieni.** Unika ślepych uliczek, np. zgadywania koloru czapki („czerwony? zielony? niebieski?”), gdzie użytkownik w końcu mówi „tak” na odczepnego. Po dwóch nieudanych próbach w tej samej sprawie pyta, czy to w ogóle ważne
- Rozmowa nie ma wyznaczonego końca. ZAKOŃCZ znaczy „na razie wychodzę”
- Wejście do modułu, jak w grach: **WRÓĆ DO ROZMOWY** (ostatnia, kafelek mówi o czym), **NOWA ROZMOWA** (czyści tylko bieżący wątek, pamięć zostaje), **CO O MNIE WIESZ**. Przy pierwszym wejściu od razu nowa rozmowa
- AI dostaje: notatki, krótkie streszczenie wcześniejszych rozmów i około 20 ostatnich wymian
- Bez internetu w pierwszej wersji: Kompan zna datę i notatki, a o bieżących sprawach mówi, że nie wie

### Charakter

- Swobodny, na „ty”, jak kolega z kolegą. Z humorem, bez udawanej radości i bez traktowania użytkownika jak dziecka albo pacjenta
- Krótkie wypowiedzi
- Sam proponuje tematy na podstawie notatek i może coś opowiedzieć, a nie tylko pytać
- Może się nie zgodzić
- Nie udaje człowieka, nie wymyśla sobie życiorysu ani faktów
- Nie zastępuje kontaktu z ludźmi: gdy pasuje, zachęca do niego
- Głos narratora, ten sam co w grach
- Nie jest lekarzem ani systemem alarmowym. Poważne sprawy traktuje poważnie, nie udziela porad medycznych i proponuje zwykłe „Przekazać to komuś?”. Nie wzywa pomocy i nie działa bez zgody

### Pamięć

- AI zapisuje samo, w trakcie rozmowy, tylko to, co przyda się później: ludzi, zainteresowania, potrzeby, preferencje. Drobiazgów nie zapisuje
- Przy każdym wpisie notuje, skąd to wie: użytkownik sam wskazał czy AI wywnioskowało lub zgadło
- Okresowy przegląd: gdy jest około 5 nowych wpisów, w naturalnej przerwie, nie w środku trudnej rozmowy. „Przy okazji, zapamiętałem: … Zgadza się?”. Przyciski: **Wszystko dobrze**, **Coś jest źle** (po jednym wpisie, można usunąć), **Nie teraz**
- Dostęp: użytkownik (CO O MNIE WIESZ: czyta i usuwa) i osoba techniczna (plik na komputerze). Nikt inny
- Dane startowe wpisywane raz ręcznie, na podstawie `user_info.json` ze starego Kompana
- Przed każdą zmianą notatek zostaje poprzednia wersja

### Prośby od innych osób

Użytkownikowi Kompan nigdy nie mówi „zadanie”.

- Prośba jest jawna: „Janek poprosił mnie, żebym zapytał, co Ci przeszkadza w programie do pisania. Porozmawiamy o tym?”. Przyciski: **Tak**, **Później**, **Nie chcę**
- Autor dostaje tylko to, co użytkownik zatwierdził, nigdy całej rozmowy
- **Później:** Kompan wraca do prośby przy następnej rozmowie. Po trzech odłożeniach pyta raz, czy powiedzieć autorowi, że użytkownik woli o tym nie rozmawiać
- **Nie chcę:** pyta, czy powiedzieć autorowi (krótko, bez powodu), czy nie (prośba się zamyka, autor nic nie dostaje). Odmowa nie trafia do notatek
- Kto może prosić: osoby z listy. Na start tylko jedna (osoba techniczna), docelowo wszystkie kontakty użytkownika w Wicero
- Treść prośby to tylko coś do przekazania, nie polecenie. Kompan zawsze mówi, kto pyta, i zawsze można odmówić, cokolwiek napisano w prośbie
- Sposób przekazania: najpierw polecenie na komputerze z AP (zdalnie przez SSH), potem Wicero

### Wiadomości

1. „Wygląda na to, że … Przekazać to komuś?” Przyciski: osoby z listy, od najlepiej pasujących, i **Nikomu**
2. „Komuś jeszcze?” Przyciski: pozostałe osoby i **To wszystko**
3. „Przekażę: …” Przyciski: **Wyślij**, **Popraw**, **Nie wysyłaj**

- Odpowiedź na prośbę idzie domyślnie do jej autora, bez kroków 1-2
- Odbiorcy tylko z listy w pliku. Wysyła kod, dopiero po „Wyślij”; AI nie może nic wysłać
- Każda wiadomość mówi, że spisał ją Kompan na podstawie rozmowy, bo AI mogło coś źle zrozumieć. Na końcu standardowa formułka: „Ta wiadomość została wygenerowana automatycznie, prosimy na nią nie odpowiadać”
- Kanał: osobne konto Gmail, hasło aplikacji tylko w `.env`. Po etapie czatu w Wicero także Wicero, wraz z odpowiedziami odbiorców
- Nieudana wysyłka czeka w kolejce i jest ponawiana; użytkownik o tym słyszy, a jeśli problem trwa, także przy następnej rozmowie

### Log, koszty, prywatność

- Pełny log, zawsze: każde pytanie, wszystkie opcje, wybrana odpowiedź i wszystkie zapytania do AI. Czyta go tylko osoba techniczna
- Kompan na razie (użytek wewnętrzny) nie ogłasza, że rozmowy są zapisywane. Nie obiecuje jednak prywatności i nie zaprzecza, gdy temat się pojawi
- Model: `claude-opus-5-5`, zmiana w `.env`. Po tygodniu porównanie z Sonnet 5.5 na prawdziwych kosztach
- Szacunek (nie pomiar, 100 pytań dziennie): Opus 5.5 ok. 45-105 $ miesięcznie, Sonnet 5.5 ok. 20-50 $
- Dzienny limit w Kompanie: 5 $ na start, w `.env`. Po przekroczeniu: „Na dziś muszę już kończyć”, rozmowa zostaje zapisana

## Architektura

```
AP (Python 2.7)                       ap-gra-kompan (Python 3, port 8768)
modules/kompan.py  --- HTTP --->      kompan/
kompan_client.py   <-- stan ---         rozmowa, pamięć, prośby, wiadomości, koszty
                                        |-- Claude API
                                        |-- Piper (nagrania)
                                        |-- Gmail (wysyłka)
                                        dane-kompan/ (tylko ta usługa)
```

- Nowa usługa w `docker-compose.yml`, z tego samego obrazu co kreator. Korzysta ze wspólnego kodu: wywołanie AI (`kreator/ai.py`), log (`engine/log.py`), narrator (`tools/nagraj.py`)
- Osobny katalog `dane-kompan/`, niewidoczny dla kreatora, rysownika i serwera gry. Poza repozytorium
- Osobny klucz API `ap-kompan`, żeby koszt był widoczny osobno
- AP nie czeka na AI: stan „mysli”, „Myślę...”, pytanie o stan co sekundę, jak w kreatorze. WRÓĆ nie pyta AI
- AI nie ma narzędzi ani dostępu do plików. Zwraca odpowiedź według schematu JSON: wypowiedź, opcje, tytuł wątku, nowe wpisy do notatek, propozycję przekazania. Kod sprawdza limity i wykonuje resztę
- Inaczej niż w kreatorze rozmowy przeżywają restart usługi, bo WRÓĆ DO ROZMOWY ma działać także następnego dnia

```
dane-kompan/
  notatki.json          wpisy: tekst, skąd wiadomo, data, czy potwierdzony
  notatki-wersje/       poprzednie wersje
  osoby.json            imię, adres, czy może prosić, czy może dostawać wiadomości
  rozmowy/<id>/         log.jsonl (pełna historia), stan.json
  streszczenie.json     skrót wcześniejszych rozmów
  prosby/<id>.json      od kogo, treść, stan, liczba odłożeń
  wiadomosci/<id>.json  kolejka wysyłki
  koszty.jsonl          koszt dzienny, liczony z tokenów
```

## Plan

Testy automatyczne w kontenerze po każdym etapie, z udawanym AI. Testy ręczne na komputerze z AP, po jednym.

**Etap 1 - usługa i rozmowa**
- [ ] Usługa `ap-gra-kompan`, `kompan/` (stany, przyciski, WRÓĆ, Blisko, Inne propozycje, Zmień temat)
- [ ] Prompt: odbiorca, charakter, zasada „pytaj tylko, gdy odpowiedź coś zmieni”
- [ ] Zapis rozmów, wznowienie po restarcie, streszczanie starszych wymian
- [ ] Notatki startowe tylko do odczytu
- [ ] Koszt z tokenów i dzienny limit

**Etap 2 - AP**
- [ ] `kompan_client.py`, `modules/kompan.py`: ekran wejścia i plansza rozmowy
- [ ] Kafelek KOMPAN na planszy NOWE (zamiast pustego pola), ikona
- [ ] Sprawdzić, czy do 7 przycisków i 2 na dole mieści się na ekranie i czy skanowanie nie jest za długie
- [ ] **Pierwszy test ręczny: czy to się dobrze rozmawia.** Główna niewiadoma, więc zanim zbudujemy resztę

**Etap 3 - pamięć**
- [ ] Zapisywanie przez AI, źródło wpisu, poprzednie wersje
- [ ] Okresowy przegląd i CO O MNIE WIESZ

**Etap 4 - wiadomości**
- [ ] `osoby.json`, przebieg wyboru osób i zatwierdzania
- [ ] Wysyłka przez Gmail, kolejka i ponawianie

**Etap 5 - prośby**
- [ ] Polecenie dodające prośbę, sprawdzenie osoby na liście
- [ ] Przebieg: Tak, Później, Nie chcę; zwrotka do autora

**Etap 6 - wyszukiwanie w internecie** (jak najszybciej po etapach 1-5)
- [ ] Sprawdzanie bieżących informacji; treść ze stron to dane, nie polecenia

**Etap 7 - Wicero** (zależy od etapu czatu w Wicero)
- [ ] Prośby od kontaktów, wiadomości i odpowiedzi odbiorców przez Wicero

**Uruchomienie (Ty)**
- [ ] Klucz API `ap-kompan` w `.env` na komputerze z AP
- [ ] Konto Gmail i hasło aplikacji w `.env` (przed etapem 4)
- [ ] Dostęp SSH do komputera z AP (przed etapem 5)
- [ ] Lista osób i notatki startowe
- [ ] Nagranie `sounds/kompan.ogg` (do tego czasu głos AP)

## Główna niewiadoma

Czy rozmowa będzie dobra na tyle, żeby użytkownik chciał do niej wracać. Dlatego rozmowa i test ręczny są przed pamięcią, wiadomościami i prośbami.

## TODO

- [ ] Samodzielne pisanie skanowaniem („Napiszę sam”) - na razie nie ma sensu
- [ ] Kopia notatek i rozmów poza laptopem - do przeanalizowania (kopia przez SSH to jedna z opcji, są lepsze)
- [ ] Mail jako awaryjna droga odpowiedzi dla osób bez Wicero
- [ ] Osobny moduł bezpieczeństwa (wzywanie pomocy) - możliwy, ale poza kompetencjami Kompana
- [ ] Jeśli Kompan wyjdzie poza użytek wewnętrzny: mówić użytkownikom, że rozmowy są zapisywane, kto może je czytać i że przechodzą przez dostawcę AI; sprawdzić stronę prawną (dane o zdrowiu, RODO)
- [ ] Przeniesienie kafelka do menu głównego, jeśli Kompan będzie często używany
