# Kompan: rozmowa z AI w AP

**Wątek:** repo `ablelab-plany`, `watki/kompan.md` (stan, kolejka, wszystkie pliki); dalszy kierunek - `watki/kompan-umiejetnosci.md`.

**Status:** projekt zatwierdzony 2026-11-08, kod etapów 1-3 gotowy (do 2026-11-09). 2026-11-14 pierwsze testy z prawdziwym AI na komputerze z AP: K1-K6 zaliczone, poprawki promptu i kosztu po K4 i K6. Kod etapu 4 (wiadomości) gotowy 2026-11-14, etapu 5 (poczta przychodząca, jeden zwiastun w AP) 2026-11-15; oba czekają na konto Gmail. Następny krok: sprawdzić poprawki na rozmowie (zasada „najpierw podstawy”), potem testy K7-K8. Testy ręczne: `KOMPAN_PLAN.md` w repo AP. Kompan to rozmówca dla użytkownika AP: rozmawia na dowolny temat, z czasem coraz lepiej go zna, może dowiedzieć się czegoś na prośbę innej osoby i przekazać to, co ważne, za zgodą użytkownika.

Pomysł pochodzi z repozytorium `kompan` (gałąź `feat/user-context-system`), a technologia z kreatora gier (`kreator-gier.md`), który działa dobrze. Kodu starego Kompana nie używamy.

## Ustalenia

### Rozmowa

- Kompan zadaje jedno pytanie naraz. Pod nim są, w pionie, 2-4 odpowiedzi od AI, a w rzędzie na dole **Blisko** (AI dopytuje, co było trafne), **Inne propozycje**, **Zmień temat**, **WRÓĆ** i **ZAKOŃCZ**
- **Pyta tylko wtedy, gdy odpowiedź coś zmieni.** Unika ślepych uliczek, np. zgadywania koloru czapki („czerwony? zielony? niebieski?”), gdzie użytkownik w końcu mówi „tak” na odczepnego. Po dwóch nieudanych próbach w tej samej sprawie pyta, czy to w ogóle ważne
- Rozmowa nie ma wyznaczonego końca. ZAKOŃCZ znaczy „na razie wychodzę”
- Wejście do modułu, jak w grach: **WRÓĆ DO ROZMOWY** (ostatnia, kafelek mówi o czym), **NOWA ROZMOWA** (czyści tylko bieżący wątek, pamięć zostaje), **CO O MNIE WIESZ**. Przy pierwszym wejściu od razu nowa rozmowa
- AI dostaje: notatki, krótkie streszczenie wcześniejszych rozmów i ostatnie 20-30 wymian. Starsze są co jakiś czas przenoszone do streszczenia, partiami, żeby działała pamięć podręczna API; stara rozmowa trafia tam w całości przed nową
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
- Dane startowe wpisywane raz ręcznie, na podstawie `user_info.json` ze starego Kompana: dowolny czytelny tekst w `dane-kompan/notatki_startowe.txt`
- Przed każdą zmianą notatek zostaje poprzednia wersja

Szczegóły przyjęte przy kodzie (2026-11-09, do zmiany po testach):
- Wpis ma najwyżej 80 znaków i jest pisany tak, jakby Kompan mówił do użytkownika („Kibicujesz Legii.”). W jednej odpowiedzi najwyżej 3 wpisy, a powtórki tego, co już jest, kod pomija
- Moment przeglądu wybiera AI. Kod pokazuje przegląd tylko wtedy, gdy czeka co najmniej 5 wpisów i AI uzna, że to dobra chwila. Co odpowiedź AI słyszy, ile wpisów czeka
- Przegląd pokazuje najwyżej 5 najstarszych wpisów. „Coś jest źle” prowadzi przez wpisy po kolei: **Dobrze**, **To nieprawda, usuń**, **Reszta jest dobra**. „Nie teraz” odkłada przegląd o 2 godziny. Przegląd nie pyta AI, więc nic nie kosztuje
- Notatki AI dostaje na końcu ostatniej wiadomości, za punktem pamięci podręcznej (2026-11-14, po K4). Wcześniej były w instrukcji systemowej i każdy nowy wpis unieważniał pamięć podręczną całej rozmowy: odpowiedź kosztowała wtedy ok. 4-5 centów zamiast ok. 1
- Usunięty wpis trafia na listę „to nieprawda” (ostatnie 20), którą AI dostaje razem z notatkami, żeby nie zapisało go ponownie
- CO O MNIE WIESZ czyta wpisy po jednym: **Dalej**, **To nieprawda, usuń**, **Wystarczy**. Przy niepotwierdzonym przypuszczeniu dodaje „To moje przypuszczenie.”. Notatek startowych tu nie ma, bo zmienia je tylko osoba techniczna

### Poczta przychodząca (nowy etap 5, decyzja 2026-11-14)

Zamiast osobnych próśb przez SSH: jedna poczta przychodząca Kompana. Odpowiedzi na wiadomości Radka, nowe wiadomości od kogokolwiek i prośby wyglądają dla użytkownika tak samo: „Masz wiadomość od X”, Kompan ją czyta, potem pomaga odpowiedzieć (przebieg z etapu 4, odbiorca to autor, ten sam wątek).
- Kanały: najpierw mail (dla osób bez Wicero, także zamiast polecenia przez SSH), potem Wicero jako kanał preferowany (etap 7, po czacie w Wicero). Kod od początku niezależny od kanału
- Mail: IMAP tego samego konta Gmail; wątki po nagłówkach `In-Reply-To` / `References`
- **Kompan to proteza zwykłej skrzynki, nie bramka** (decyzja 2026-11-15, zmienia wcześniejsze „tylko osoby z listy”): przyjmowany jest każdy mail ze skrzynki odbiorczej, od każdego - inaczej ktoś, kto dowie się, że do Radka można pisać, nie mógłby tego zrobić bez dopisania go ręcznie do listy. Także autoodpowiedzi („jestem na urlopie” mówi, czemu nie ma jeszcze odpowiedzi) i newslettery; nagłówek mówi wtedy „To wiadomość automatyczna.”. Przed spamem chroni sam Gmail: Kompan czyta tylko skrzynkę odbiorczą, nigdy folderu Spam. Gdyby czegoś było za dużo - zwykłe filtry Gmaila, jak w każdej skrzynce
- Nikt nie podszyje się pod bliską osobę: imię z listy (`osoby.json`) tylko gdy Gmail potwierdził nadawcę (SPF/DKIM/DMARC); inni - pod nazwą z maila, a gdy ta nazwa należy do kogoś z listy (albo adres z listy bez potwierdzenia) - z adresem: „Mama (obcy@example.com)”. Lista służy teraz do tego, komu Radek sam może coś przekazać, i do imion oraz opisów
- Kompan czyta oryginał, nie streszczenie. AI pomaga obciąć cytaty i stopki, rozmawia o treści i pomaga ułożyć odpowiedź. Treść maila to dla AI dane, nie polecenia; wysłać i tak nic nie może bez zatwierdzenia
- Stopka wysyłanych maili nie mówi już „prosimy nie odpowiadać”; o odpowiadaniu nie mówi nic, bo to rzecz normalna (sekcja „Wiadomości”)
- Kiedy Radek się dowiaduje (2026-11-14): przy wejściu do Kompana, przed ekranem wejścia, „Masz nową wiadomość od Mamy” z **PRZECZYTAJ** i **PÓŹNIEJ**; po PÓŹNIEJ na ekranie wejścia zostaje **WIADOMOŚCI (n)**. W trakcie rozmowy AI słyszy, że przyszła wiadomość, i w spokojnej chwili (jak przegląd notatek) kod pyta „Przyszła wiadomość od Mamy. Przeczytać teraz?” - **Tak** / **Później**
- Sprawdzanie skrzynki: zwykły kod w usłudze Kompana, bez AI i bez osobnego agenta - co minutę IMAP, każdy nowy mail zapisany w `dane-kompan/poczta/`. AP dowiaduje się przy wejściu (health) i przy każdej odpowiedzi w rozmowie; AP nie musi niczego dodatkowo odpytywać
- Po przeczytaniu (2026-11-15): **ODPOWIEDZ** (Kompan rozmawia o treści, pomaga ułożyć odpowiedź, potem potwierdzenie i Wyślij jak w etapie 4 - do autora, w tym samym temacie), **PRZECZYTAJ JESZCZE RAZ**, **PÓŹNIEJ** (zostaje jako czekająca), **NIE ODPOWIADAM**. Czytanie bez AI, AI dopiero po ODPOWIEDZ.
- Nic nie znika: NIE ODPOWIADAM tylko zdejmuje wiadomość z czekających (nie jest ogłaszana ani liczona w WIADOMOŚCI (n)). Kompan mówi wtedy, gdzie ją znaleźć („Gdybyś zmienił zdanie, znajdziesz ją w WIADOMOŚCIACH, u Mamy.”)
- WIADOMOŚCI to korespondencja, nie skrzynka do załatwienia: **osoba → tematy → wiadomości**. Osoby: najpierw z nowymi, potem od ostatniego kontaktu (Inne osoby). Tematy: od najświeższego (Inne tematy). Wiadomości w temacie: od najnowszej, **Wcześniejsza** / **ODPISZ Z KOMPANEM** / **Wystarczy**; w temacie także wiadomości wysłane przez Radka („Ty napisałeś: …”). ODPISZ Z KOMPANEM zawsze, także przy starych i zamkniętych
- Skróty: nowa wiadomość (z ogłoszenia przy wejściu i z WIADOMOŚCI (n)) - prosto do treści; osoba z jednym tematem - bez poziomu tematów
- Tematy bez AI: mail - wątek po nagłówkach, nowy mail to nowy temat. Wiadomości Radka mają temat z tytułu rozmowy (w mailu i w AP „Leki”). Cudze maile - temat od nadawcy, a gdy pusty albo „Re:” / „Fw:” - pierwsze słowa treści. ODPISZ zawsze w tym samym temacie; nowa sprawa z rozmowy to nowy temat
- Czat Wicero: jeszcze nie przeanalizowany (osobny temat, może przynieść własne pomysły, np. tematy w czacie). Model korespondencji nie może zakładać, jak będzie wyglądał - kanał dostarcza wiadomości z przypisaniem do tematu, a jak czat Wicero będzie je dzielił, ustalimy przy jego projekcie
- **Bez osobnych próśb** (2026-11-15): prośba to zwykła wiadomość („Radek, co Ci przeszkadza w programie do pisania?”), czytana w oryginale i obsługiwana przez ODPOWIEDZ. Nie wymagamy od piszących wiedzy, że po drodze jest AI, ani specjalnych oznaczeń. Kompan może po przeczytaniu zaproponować „Porozmawiamy o tym?”. Gdyby kiedyś był potrzebny temat zlecony Kompanowi do poruszenia w rozmowie bez czytania listu - osobny rodzaj wiadomości, model to udźwignie
- Długie maile i załączniki (2026-11-15), bez AI: nagłówek („Od Mamy, wczoraj o 18:40. Leki.”), treść w częściach na granicach akapitów i zdań z **Dalej** („To dłuższa wiadomość, 4 części.”), HTML zamieniany na tekst, linki czytane jako „link” i nieotwierane, nagrania robione w tle zaraz po przyjściu maila. Załączniki: tylko informacja („Są załączniki: 2 zdjęcia i plik PDF, których nie pokażę.”)

### Powiadomienia i korespondencja w całym AP (decyzja 2026-11-15)

Temat globalny, ustalony przed szczegółami poczty, bo dotyczy też Wicero. Stan wyjściowy: w AP działa jeden zwiastun - `Notifier` w `modules/wicero.py` (repo AP), uruchamiany w menu głównym. Co minutę pyta serwer Wicero, co powiedzieć (nowy film raz, nieotwarte przy starcie i co godzinę - decyduje serwer), i mówi to w każdym miejscu AP poza modułem Wicero.

Układ docelowy - trzy warstwy:

| Warstwa | Co robi | Gdzie |
|---|---|---|
| Źródła | Wiedzą, co nowego, i decydują, co i kiedy ogłosić | Wicero (filmy, później czat) i serwer Kompana (maile). Ta sama umowa: lista zdań do powiedzenia teraz |
| Jeden zwiastun w AP | Pyta wszystkie źródła, mówi po kolei, nigdy dwa naraz; nie mówi w module, którego dotyczy ogłoszenie | Obecny `Notifier`, rozszerzony o źródło Kompan (wzorce z T10 / BUG 2 - kopiować, nie przerabiać) |
| Miejsca działania | Tam się coś z tym robi | Filmy: moduł Wicero (bez zmian). Korespondencja tekstowa (mail teraz, czat Wicero potem): Kompan, bo odpowiedź trzeba ułożyć, a w tym pomaga AI |

Zasady:
- **Ogłaszanie i czytanie bez AI, odpowiadanie z AI.** Powiadomienia i odczyt wiadomości działają też bez internetu do AI, po dziennym limicie i bez klucza. AI tylko pomaga zrozumieć i ułożyć odpowiedź
- Korespondencja w Kompanie niezależna od kanału: wątek z osobą, kanał mail albo Wicero, Wicero preferowane, gdy osoba je ma
- Nie osobne moduły (dwa zwiastuny mówiące naraz, osobny moduł na maile) i nie wszystko w Kompanie (zależność od płatnego AI, przenoszenie działającego filmu bez korzyści)
- Most film ↔ Kompan (później): Kompan wie o nowym filmie i może o nim porozmawiać; przycisk otwiera zwykły odtwarzacz Wicero, po filmie AP wraca na planszę Kompana, a AI dostaje „(Radek obejrzał film od Mamy)”. Kod AP, nie umiejętność AI

Zarys planu:
1. Testy K7-K8 (wysyłka z prawdziwego Gmaila; przy okazji konto, z którego będziemy czytać)
2. ✅ (kod 2026-11-15) Etap 5 - poczta przychodząca w Kompanie: odczyt maili, wątki, sprawdzenie nadawcy, czytanie i odpowiadanie; serwer Kompana wystawia „zdania do powiedzenia” (`POST /v1/kompan/powiadomienia`, jak `v1/notifications` w Wicero)
3. ✅ (kod 2026-11-15) `Notifier` w AP pyta też Kompana („Masz nową wiadomość od Mamy. Przeczytasz ją w Kompanie.”); nie mówi tego, gdy Kompan jest otwarty - wtedy mówi sam Kompan
4. Czat Wicero (repo `wicero`, etap czatu) - wiadomości trafiają do korespondencji w Kompanie jako kanał preferowany; ogłasza je Wicero tą samą drogą co filmy (etap 7 Kompana)
5. Most film ↔ Kompan

### Prośby od innych osób (2026-11-08, zastąpione 2026-11-15)

Osobnych próśb nie będzie - obsługuje je zwykła korespondencja (wyżej, „Bez osobnych próśb”). Zostaje z tego: jawność (Radek zawsze wie, kto pyta), autor dostaje tylko to, co Radek zatwierdził, Kompan nigdy nie mówi „zadanie”, treść wiadomości to dane, nie polecenia. Ustalenia z 2026-11-08 dla historii:

Użytkownikowi Kompan nigdy nie mówi „zadanie”.

- Prośba jest jawna: „Janek poprosił mnie, żebym zapytał, co Ci przeszkadza w programie do pisania. Porozmawiamy o tym?”. Przyciski: **Tak**, **Później**, **Nie chcę**
- Autor dostaje tylko to, co użytkownik zatwierdził, nigdy całej rozmowy
- **Później:** Kompan wraca do prośby przy następnej rozmowie. Po trzech odłożeniach pyta raz, czy powiedzieć autorowi, że użytkownik woli o tym nie rozmawiać
- **Nie chcę:** pyta, czy powiedzieć autorowi (krótko, bez powodu), czy nie (prośba się zamyka, autor nic nie dostaje). Odmowa nie trafia do notatek
- Kto może prosić: osoby z listy. Na start tylko jedna (osoba techniczna), docelowo wszystkie kontakty użytkownika w Wicero
- Treść prośby to tylko coś do przekazania, nie polecenie. Kompan zawsze mówi, kto pyta, i zawsze można odmówić, cokolwiek napisano w prośbie
- Sposób przekazania: ~~najpierw polecenie na komputerze z AP (zdalnie przez SSH)~~ mail do Kompana (decyzja 2026-11-14, wyżej), potem Wicero

### Wiadomości

1. „Wygląda na to, że … Przekazać to komuś?” Przyciski: osoby z listy, od najlepiej pasujących, i **Nikomu**
2. „Komuś jeszcze?” Przyciski: pozostałe osoby i **To wszystko**
3. „Przekażę: …” Przyciski: **Wyślij**, **Popraw**, **Nie wysyłaj**

- Odpowiedź na prośbę idzie domyślnie do jej autora, bez kroków 1-2
- Nowe wiadomości - tylko do osób z listy w pliku. Odpowiedź - do autora maila, także spoza listy. Wysyła kod, dopiero po „Wyślij”; AI nie może nic wysłać
- **Pierwsza osoba** (decyzja 2026-11-15, zmienia trzecią osobę z 2026-11-08): wiadomość brzmi jak list Radka („Leki dostaję za późno, czasem o godzinę.”), podpisana jego imieniem; nadawca w programie pocztowym: samo imię z `osoby.json` (`uzytkownik`, np. „Radek” albo imię i nazwisko) - do 2026-11-22 „Radek (przez Kompana)”, zmienione, bo o pomocy Kompana mówi stopka
- **Powitanie** (2026-11-15): AI proponuje je osobno (pole `przekaz.powitanie`, najwyżej 40 znaków) w tonie z opisu osoby („Cześć Mamo,”, „Dzień dobry, Panie Profesorze,”); dla kilku osób wspólne, bez imienia („Cześć,”). Gdy Radek wybierze inne osoby niż te, które AI powitało - „Dzień dobry,” (zawsze może Poprawić). W ciągnącym się wątku bez powitania: pierwsza wiadomość Radka w temacie (nowa sprawa albo pierwsza odpowiedź) - z powitaniem, kolejne - bez. Treść najwyżej 220 znaków, żeby z powitaniem zmieściła się na ekranie potwierdzenia
- **Stopka o AI pod każdą wiadomością**, krótka, zwykłym tekstem, widoczna na równi z treścią (bez linii „-- ”, którą programy pocztowe często wyszarzają): „Ta wiadomość powstała z pomocą Kompana, asystenta AI. W sformułowaniach mogą zdarzyć się nieścisłości.” Odpowiadanie jest czymś normalnym, więc o nim nic - odpisać może każdy. Stopka jest bez form rodzajowych i odmiany imienia, więc pasuje do każdego użytkownika
- Kanał: osobne konto Gmail, hasło aplikacji tylko w `.env`. Po etapie czatu w Wicero także Wicero, wraz z odpowiedziami odbiorców
- Nieudana wysyłka czeka w kolejce i jest ponawiana; użytkownik o tym słyszy, a jeśli problem trwa, także przy następnej rozmowie

Szczegóły przyjęte przy kodzie (2026-11-14, do zmiany po testach K7-K8):
- AI proponuje przekazanie w polu `przekaz` (pytanie, treść, proponowani odbiorcy). Przebieg pokazuje kod, przed zwykłą wypowiedzią AI, jak przegląd notatek. Bez konta Gmail albo bez osób na liście AI dostaje „lista jest pusta” i nic nie proponuje
- Kolejność osób: najpierw te, które wskazało AI, potem reszta listy. Mieszczą się 3 osoby i „Nikomu”; przy większej liście po 2 osoby na stronę i **Inne osoby** (strony w kółko)
- Gdy wybrano wszystkie osoby z listy, „Komuś jeszcze?” jest pomijane
- Potwierdzenie: „Wiadomość dla: Mama, Jurek”, treść, „Wysłać?”. Treść najwyżej 220 znaków i powitanie najwyżej 40, żeby zmieściły się na ekranie. Nagrywane w chwili wyboru, więc AP czeka na nie kilka sekund
- **Popraw** wraca do rozmowy: AI dopytuje, co zmienić (odpowiedzi do wyboru), i proponuje nową treść; odbiorcy zostają ci sami, więc od razu jest potwierdzenie
- Jedna wiadomość na odbiorcę, wysyłana osobno (odbiorcy nie widzą swoich adresów). Temat: tytuł rozmowy (bez tytułu: „Wiadomość od: Radek”). Treść: powitanie, wiadomość w pierwszej osobie, imię, stopka o AI (wyżej)
- O wyniku (wysłana do kolejki / nic nie wysłano / nieudana wysyłka / w końcu wysłana) AI dowiaduje się raz, dopisane do następnego wyboru użytkownika; o wiadomościach, które wciąż czekają, także na początku nowej rozmowy
- AI nie zna adresów, tylko imiona, to, kim są, i opisy

`dane-kompan/osoby.json` (wpisuje osoba techniczna; zmiana działa bez restartu):
```
{"uzytkownik": "Radek",
 "osoby": [{"imie": "Jurek", "kto": "brat", "email": "...", "wiadomosci": true,
            "opis": "Brat Radka, programista. Swobodnie, po bratersku, można żartować."},
           {"imie": "Profesor", "kto": "prowadzący zajęcia", "email": "...", "wiadomosci": true,
            "opis": "Prof. Nowak. Forma „Panie Profesorze”, uprzejmie i swobodnie, ale nie jak do kolegi. Bez zdrobnień."}]}
```
`wiadomosci`: można mu coś przekazać. Pisać do Kompana może każdy, także spoza listy (wyżej, „Poczta przychodząca”); flaga `pisze` (wcześniej `prosby`) usunięta 2026-11-15, stare pole w pliku jest pomijane; `opis` (nieobowiązkowy, 2026-11-15): kim jest dla Radka i jak do niego pisać - zwykły tekst, kilka zdań. Idzie do AI z listą osób (w buforowanej części promptu, więc prawie nic nie kosztuje) i ustawia ton wiadomości i propozycji odpowiedzi, nigdy treść. Pisze go osoba techniczna; to, czego Kompan dowie się w rozmowie, idzie do notatek. Opis trafia do API przy każdej rozmowie, gdy wiadomości są włączone - nie wpisywać tam niczego, czego nie chcemy tam wysyłać.

### Log, koszty, prywatność

- Pełny log, zawsze: każde pytanie, wszystkie opcje, wybrana odpowiedź i wszystkie zapytania do AI. Czyta go tylko osoba techniczna
- Kompan na razie (użytek wewnętrzny) nie ogłasza, że rozmowy są zapisywane. Nie obiecuje jednak prywatności i nie zaprzecza, gdy temat się pojawi
- Model: `claude-opus-5-5`, zmiana w `.env`. Po tygodniu porównanie z Sonnet 5.5 na prawdziwych kosztach
- Szacunek (nie pomiar, 100 pytań dziennie): Opus 5.5 ok. 45-105 $ miesięcznie, Sonnet 5.5 ok. 20-50 $
- Dzienny limit w Kompanie: 5 $ na start, w `.env`. Po przekroczeniu: „Na dziś muszę już kończyć”, rozmowa zostaje zapisana
- Pierwszy tydzień (2026-11-21): ok. 5 $ za wieczór rozmowy, limit przerwał wiersz w połowie. Od 2026-11-21 (`kompan/koszty.py` `answers_left`, `kompan/rozmowa.py`): gdy na dziś zostaje najwyżej 15 odpowiedzi (szacunek ze średniej ostatnich), AI dostaje „(Na dziś zostało jeszcze około N odpowiedzi.)”, a przy ostatniej „(To prawdopodobnie ostatnia odpowiedź na dziś.)” - mówi o tym raz i proponuje dokończyć to, co trwa. Powrót do rozmowy przerwanej limitem: AI dostaje „(Wracacie po przerwie...)”. Nowa rozmowa po limicie: w otwarciu tytuł i 3 ostatnie wymiany przerwanej rozmowy, żeby AI mogło zaproponować dokończenie (np. wiersza)

### Testy bez psucia danych (2026-11-15)

Od 2026-11-15 Radek używa Kompana na co dzień: `dane-kompan/` to prawdziwe dane (notatki, rozmowy, streszczenie, koszty), których nie wolno zgubić ani zaśmiecić testami.
- **Osobna instancja testowa** `ap-gra-kompan-test` (profil `test` w `docker-compose.yml`): ten sam kod, port 8769, własne dane `dane-kompan-test/`, własny plik `.env.kompan-test` (osobny klucz API `ap-kompan-test` - koszty testów osobno także w konsoli Anthropic - i własny dzienny limit). Uruchamiana tylko na czas testów
- AP rozmawia z nią, gdy jest uruchomione z `AP_KOMPAN_URL=http://localhost:8769`. Ekran wejścia mówi wtedy „Kompan, wersja testowa”, a `health` ma `"test": true` - nie da się pomylić
- Prawdziwa instancja w tym czasie działa dalej, ale z nią nic się nie dzieje: rozmowy, notatki, logi i koszty testów są tylko w `dane-kompan-test/`
- Poczta: dwie instancje nie mogą czytać tej samej skrzynki (jedna oznaczyłaby maile drugiej jako przeczytane). Na testy K7-K10 Gmail ma tylko instancja testowa, a prawdziwa dostaje go po testach. Później, do kolejnych testów poczty - osobne konto Gmail testowe. W `osoby.json` testowej instancji tylko adresy osoby technicznej
- Kopia `dane-kompan/` przed każdą aktualizacją (`tar` do `~/kopie-kompan/`), potem porównanie liczby notatek i ostatniej rozmowy - robi to `tools/kompan-aktualizuj.sh`, opis kroków w `KOMPAN_PLAN.md` (AP); nowa wersja czyta dane starszych (test `test_data_from_stage_3_still_works`)
- „Czysty stan” (przeniesienie `dane-kompan/` na bok) był jednorazowy - przed oddaniem Kompana. Na prawdziwych danych go nie robimy

## Architektura

```
AP (Python 2.7)                       ap-gra-kompan (Python 3, port 8768)
modules/kompan.py  --- HTTP --->      kompan/
kompan_client.py   <-- stan ---         rozmowa, pamięć, wiadomości, poczta, koszty
                                        |-- Claude API
                                        |-- Piper (nagrania)
                                        |-- Gmail (wysyłka SMTP, odbiór IMAP)
                                        dane-kompan/ (tylko ta usługa)
```

- Nowa usługa w `docker-compose.yml`, z tego samego obrazu co kreator. Korzysta ze wspólnego kodu: wywołanie AI (`kreator/ai.py`), log (`engine/log.py`), narrator (`tools/nagraj.py`)
- Osobny katalog `dane-kompan/`, niewidoczny dla kreatora, rysownika i serwera gry. Poza repozytorium
- Osobny klucz API `ap-kompan` w `.env.kompan`, żeby koszt był widoczny osobno
- AP nie czeka na AI: stan „mysli”, „Myślę...”, pytanie o stan co sekundę, jak w kreatorze. WRÓĆ nie pyta AI
- AI nie ma narzędzi ani dostępu do plików. Zwraca odpowiedź według schematu JSON: wypowiedź, opcje, tytuł wątku, nowe wpisy do notatek, propozycję przekazania. Kod sprawdza limity i wykonuje resztę
- Inaczej niż w kreatorze rozmowy przeżywają restart usługi, bo WRÓĆ DO ROZMOWY ma działać także następnego dnia

```
dane-kompan/
  notatki_startowe.txt  dane startowe, wpisane ręcznie
  rozmowy/<id>/         log.jsonl (pełna historia), stan.json
  streszczenie.json     skrót wcześniejszych rozmów
  koszty.jsonl          koszt każdej odpowiedzi AI, liczony z tokenów
  nagrania/             nagrania narratora
  notatki.json          wpisy: tekst, skąd wiadomo, data, czy potwierdzony; lista „to nieprawda”
  notatki-wersje/       poprzednie wersje notatek
  osoby.json            (etap 4, wpisuje osoba techniczna) imię, kto, adres, czy można coś przekazać, opis
  wiadomosci/<id>.json  (etap 4) kolejka wysyłki; wiadomosci.jsonl - log wysyłki
  poczta/               (etap 5) korespondencja w obie strony: osoba, temat, treść, stan; poczta.jsonl - log
Instancja testowa ma to samo w dane-kompan-test/ (sekcja „Testy bez psucia danych”).
```

## Plan

Testy automatyczne w kontenerze po każdym etapie, z udawanym AI. Testy ręczne na komputerze z AP, po jednym.

**Etap 1 - usługa i rozmowa** (kod gotowy 2026-11-08; testy z udawanym AI, usługa uruchomiona w kontenerze)
- [x] Usługa `ap-gra-kompan`, `kompan/` (stany, przyciski, WRÓĆ, Blisko, Inne propozycje, Zmień temat)
- [x] Prompt: odbiorca, charakter, zasada „pytaj tylko, gdy odpowiedź coś zmieni”; kod odrzuca odpowiedź z więcej niż jednym pytaniem
- [x] Zapis rozmów, wznowienie po restarcie, streszczanie starszych wymian
- [x] Notatki startowe tylko do odczytu
- [x] Koszt z tokenów i dzienny limit
- [x] Pierwsze prawdziwe zapytanie i prawdziwy koszt (2026-11-14): ok. 1 cent za zwykłe pytanie, 2,6 centa za pierwsze w rozmowie; skoki do 4-5 centów po każdym nowym wpisie usunięte przeniesieniem notatek za punkt pamięci podręcznej

**Etap 2 - AP** (kod gotowy 2026-11-08; logika planszy na atrapie `wx`, klient z Pythona 2.7 przeciw prawdziwemu serwerowi z udawanym AI)
- [x] `kompan_client.py`, `modules/kompan.py`: ekran wejścia i plansza rozmowy
- [x] Kafelek KOMPAN na planszy NOWE (zamiast pustego pola), ikona
- [x] Sprawdzić, czy 4 odpowiedzi i 5 przycisków na dole mieszczą się na ekranie i czy skanowanie nie jest za długie (K2, 2026-11-14)
- [x] **Pierwszy test ręczny: czy to się dobrze rozmawia.** (K4, 2026-11-14) Sprawnie doszedł do sedna sprawy. Poprawione: jeden wpis zamiast kilku wersji tej samej sprawy; osoby pomagające tylko po imieniu albo „osoby, które Ci pomagają”

**Etap 3 - pamięć** (kod gotowy 2026-11-09; testy z udawanym AI, w tym klient z Pythona 2.7 przeciw prawdziwemu serwerowi). Zbudowany przed testem K4 na prośbę użytkownika, żeby nie czekać; jeśli K4 pokaże, że rozmowa wymaga zmian, poprawimy głównie prompt
- [x] Zapisywanie przez AI, źródło wpisu, poprzednie wersje
- [x] Okresowy przegląd i przycisk CO O MNIE WIESZ na ekranie wejścia
- [x] Test K6 na komputerze z AP (2026-11-14). Uwaga użytkownika: przy nowym temacie AI od razu zgadywało szczegóły z typowego przebiegu (osoba ze szkoły = rówieśnik). Dopisana zasada „Najpierw podstawy, potem szczegóły” - do sprawdzenia na rozmowie

**Etap 4 - wiadomości** (kod gotowy 2026-11-14; testy z udawanym AI i udawanym Gmailem, plansza na atrapie `wx`). Zbudowany, zanim komputer z AP wrócił do testów - niezależny od nich: przebieg i wysyłkę robi kod, a ewentualne poprawki rozmowy dotyczą promptu
- [x] `osoby.json`, przebieg wyboru osób i zatwierdzania
- [x] Wysyłka przez Gmail, kolejka i ponawianie
- [x] Pierwsza osoba, powitanie, krótka stopka o AI (2026-11-15)
- [ ] Testy K7-K8 na instancji testowej (potrzebne konto Gmail i `osoby.json`)

**Etap 5 - poczta przychodząca** (zamiast próśb przez SSH, decyzja 2026-11-14; układ powiadomień 2026-11-15; kod gotowy 2026-11-15 - testy z udawanym AI, udawaną skrzynką IMAP i udawanym Gmailem, plansza i `Notifier` na atrapach `wx`, klient z Pythona 2.7 przeciw prawdziwemu serwerowi)
- [x] Układ docelowy powiadomień i korespondencji (wyżej, „Powiadomienia i korespondencja w całym AP”)
- [x] Szczegóły (wyżej, „Poczta przychodząca”)
- [x] Odczyt maili (IMAP), wątki, sprawdzenie nadawcy, obcięcie cytatów (`kompan/poczta.py`)
- [x] WIADOMOŚCI (osoba → tematy → wiadomości), ogłoszenie przy wejściu i w trakcie rozmowy, odpowiedź przez przebieg z etapu 4 (`kompan/skrzynka.py`, `kompan/rozmowa.py`)
- [x] `POST /v1/kompan/powiadomienia` i drugie źródło w `Notifier` (AP, `modules/wicero.py`)
- [x] Skrzynka jak zwykła poczta: każdy może pisać, automaty oznaczane, ochrona przed podszyciem (2026-11-15)
- [ ] Testy K9-K10 na instancji testowej (po K7-K8)

Szczegóły przyjęte przy kodzie etapu 5 (2026-11-15, do zmiany po testach):
- Skrzynka sprawdzana co minutę; mail czytany bez oznaczania jako przeczytany i oznaczany dopiero po zapisaniu, więc awaria w środku nie gubi maila. Każdy przyjęty mail jest w `dane-kompan/poczta.jsonl` (`mail_przyjety`: adres, czy z listy, czy nadawca potwierdzony, czy automat)
- Sprawdzenie nadawcy (decyduje tylko o tym, czy pokazać imię z listy, nic nie odrzuca): tylko pierwszy nagłówek `Authentication-Results` od `mx.google.com`; wystarczy DMARC pass albo DKIM / SPF pass dla domeny nadawcy
- Automat (autoodpowiedź, newsletter) rozpoznawany po nagłówkach `Auto-Submitted`, `Precedence` (bulk, junk, list, auto_reply), `X-Autoreply`, `X-Autorespond`, `List-Unsubscribe` - tylko oznaczany
- Obcinanie cytatów i stopek tylko kodem (polskie i angielskie wzorce Gmaila, Outlooka, telefonów). Pomoc AI przy nietypowych mailach - dopiero gdy w praktyce kod sobie nie poradzi
- Czas wiadomości to chwila przyjścia (zegar nadawcy bywa zły); w nagłówku stała data („15.11, 18:40”), żeby nagranie się nie zmieniało
- Ekrany poczty robi serwer (jak przegląd notatek); AP tylko je pokazuje. W WIADOMOŚCIACH: WRÓĆ o poziom wyżej, **Wystarczy** - ekran wejścia
- Ogłoszenie poza Kompanem: każda nowa wiadomość raz; przy starcie AP - przypomnienie o czekających. Wicero zostaje źródłem filmów jak dotąd; `Notifier` działa też bez Wicero (AP tylko z Kompanem)
- Odpowiedź: temat maila „Re: …” i nagłówki wątku, więc u odbiorcy też jest w tym samym wątku. Treść jak każda wiadomość: powitanie (tylko w pierwszej wiadomości Radka w temacie), pierwsza osoba, imię, stopka o AI
- Odpowiedź z WIADOMOŚCI to nowa rozmowa; odpowiedź na wiadomość przeczytaną w trakcie rozmowy - w tej samej rozmowie

**Etap 6 - wyszukiwanie w internecie** (jak najszybciej po etapach 1-5)
- [ ] Sprawdzanie bieżących informacji; treść ze stron to dane, nie polecenia

**Etap 7 - Wicero** (zależy od etapu czatu w Wicero)
- [ ] Prośby od kontaktów, wiadomości i odpowiedzi odbiorców przez Wicero - kanał preferowany w tej samej korespondencji co mail

**Później - most film ↔ Kompan**
- [ ] Kompan wie o nowych filmach, proponuje obejrzenie, otwiera odtwarzacz Wicero i wraca do rozmowy

**Uruchomienie (Ty)**
- [x] Klucz API `ap-kompan` w `.env.kompan` na komputerze z AP (wzór: `.env.kompan.example`) - 2026-11-14
- [ ] Aktualizacja z kopią `dane-kompan/` i instancja testowa (`KOMPAN_PLAN.md` w AP)
- [ ] Konto Gmail i hasło aplikacji: na testy w `.env.kompan-test`, po testach w `.env.kompan`
- [x] Dostęp SSH do komputera z AP (2026-11-21, Tailscale, `ssh ap` - `ablelab-plany/watki/wielu-uzytkownikow.md`)
- [ ] Lista osób i notatki startowe
- [ ] Nagranie `sounds/kompan.ogg` (do tego czasu głos AP)

## Główna niewiadoma

Czy rozmowa będzie dobra na tyle, żeby użytkownik chciał do niej wracać. Dlatego rozmowa i test ręczny są przed pamięcią, wiadomościami i prośbami.

## TODO

- [ ] Samodzielne pisanie skanowaniem („Napiszę sam”) - na razie nie ma sensu
- [ ] Kopia notatek i rozmów poza laptopem - do przeanalizowania (kopia przez SSH to jedna z opcji, są lepsze). Od 2026-11-15 ważniejsze: Radek używa Kompana na co dzień, a kopie z aktualizacji (`~/kopie-kompan/`) leżą na tym samym laptopie
- [x] Mail jako droga odpowiedzi dla osób bez Wicero - wchodzi do etapu 5 (2026-11-14)
- [ ] Zdjęcia z maili na ekranie AP (później; razem z mostem film ↔ Kompan)
- [ ] Przycisk STREŚĆ przy bardzo długich mailach (AI, wyraźnie jako streszczenie) - bardzo daleko, na razie nie ma takich maili
- [ ] Osobny moduł bezpieczeństwa (wzywanie pomocy) - możliwy, ale poza kompetencjami Kompana
- [ ] Jeśli Kompan wyjdzie poza użytek wewnętrzny: mówić użytkownikom, że rozmowy są zapisywane, kto może je czytać i że przechodzą przez dostawcę AI; sprawdzić stronę prawną (dane o zdrowiu, RODO)
- [ ] Przeniesienie kafelka do menu głównego, jeśli Kompan będzie często używany
- [ ] Sprzątanie starych nagrań: każde pytanie to szacunkowo ok. 1 MB w `dane-kompan/nagrania/` i drugie tyle w `~/.ap-gra/nagrania/`, a nic ich nie usuwa. Zmierzyć po pierwszych tygodniach (`du -sh`) i wtedy ustalić, co kasować
