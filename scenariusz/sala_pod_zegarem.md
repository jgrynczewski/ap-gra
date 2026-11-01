# Sala pod zegarem

// Akt 1 - Wiersze: od pierwszego wiersza do drzwi auli (trzy tropy: kronika,
// pani Wanda, Ola). Akt 2 - Sala pod zegarem: zeszyt Janka, dyrektor.
// Akt 3 - Szyfr i prawda: 7 zakończeń. Rozgrywka: ok. 6-15 wyborów
// (8-12 minut). Prawda i postacie - docs/fabula.md.

## start
Styczeń, poniedziałek, ósma rano. Na tablicy w sali polskiego ktoś napisał kredą wiersz:

| Z kurzu i mroku wstanie dawna pieśń.
| Echem powróci to, co w ciszy zgasło.
| Gdzie nikt nie wchodzi od dwudziestu zim,
| A drzwi zamknięto, by ukryć hasło.
| Rozpoznasz drogę, jeśli umiesz czytać.

Klasa się śmieje. A ty widzisz, że pierwsze litery wersów układają się w słowo "zegar".

* Powiedz o tym Kubie -> kuba_1
* Powiedz Oli, która stoi przy oknie -> ola_1
* Zachowaj to dla siebie -> radiowezel +bartek_patrzy
* Zapytaj pana Zielińskiego, kto to napisał -> zielinski_1

## kuba_1
Kuba słucha z otwartymi ustami. "Wieszcz, jesteś geniuszem!" - krzyczy na całą klasę. "Tam jest ukryte słowo!"

Wszyscy się odwracają. Teraz już cała szkoła będzie wiedziała, że coś wiesz.

* Ucisz go, zanim powie więcej -> radiowezel +kuba_wie
* Obróć wszystko w żart -> radiowezel +kuba_wie +zart
* Rozejrzyj się, kto słucha -> radiowezel +kuba_wie +bartek_patrzy

## ola_1
Ola słucha w milczeniu. Przy słowie "zegar" coś zmienia się w jej twarzy.

"W tej szkole jest tylko jeden zegar, który stoi od lat" - mówi cicho. - "W starej auli."

* Obiecaj, że nikomu nie powiesz -> radiowezel +zaufanie_oli
* Zapytaj, skąd to wie -> radiowezel +ola_unika
* Zaproponuj, żebyście poszli tam razem -> radiowezel +zaufanie_oli +ola_razem

## zielinski_1
Pan Zieliński wchodzi do klasy, widzi wiersz i staje. Trwa to tylko chwilę, ale ty to zauważasz.

"Ładne" - mówi i szybko ściera tablicę. Kiedy odkłada gąbkę, ręka lekko mu drży.

> ustaw: zielinski_dziwny

* Zapytaj wprost, czy wie, kto to napisał -> radiowezel +zielinski_pytany
* Nic nie mów i patrz, co zrobi -> radiowezel

## radiowezel
[bartek_patrzy] Kątem oka widzisz, że Bartek z samorządu długo patrzy na tablicę, a potem szybko odwraca wzrok.
[zart] Klasa jeszcze chichocze z twojego żartu o poecie-widmie.
[ola_unika] Ola zbyła twoje pytanie: "Po prostu wiem". I od tej pory nie patrzy ci w oczy.
[zielinski_pytany] "Wiersze piszą się same, Wieszczu" - odpowiedział pan Zieliński. I nie powiedział nic więcej.

Na przerwie trzeszczy radiowęzeł. Dyrektor Kowal ogłasza, że po studniówce stara aula pójdzie do przebudowy.

"I żadnej muzyki na studniówce, dopóki ktoś bazgrze wierszyki po tablicach" - dodaje.

Kuba blednie. To jego zespół, a ty piszesz mu teksty.

* Pociesz Kubę -> szafka +kuba_przyjaciel
* Idź do dyrektora i zapytaj, dlaczego akurat aula -> dyrektor_1
* Zignoruj to, masz własną zagadkę -> szafka

## dyrektor_1
Dyrektor Kowal przyjmuje cię w gabinecie, nie odrywając wzroku od papierów. Kiedy pytasz o aulę, odkłada długopis.

"To nie twoja sprawa" - mówi za szybko. Jego wzrok na moment ucieka do szuflady biurka.

> ustaw: dyrektor_nerwowy

* Przeproś i wyjdź -> szafka
* Zapytaj, co takiego jest w tej auli -> szafka +dyrektor_zly

## szafka
[kuba_przyjaciel] Kuba trochę odżył. "Coś wymyślimy, Wieszczu. Zawsze coś wymyślamy."
[dyrektor_zly] Na korytarzu słyszysz za plecami: "Ten od wierszyków podpadł dyrektorowi". Wieść rozeszła się szybko.

Po lekcjach znajdujesz w szafce złożoną kartkę:

| Gdzie echo śpi, tam czas się zatrzymał.
| Kto zna słowa, ten znajdzie klucz.

Ktoś wie, że rozgryzłeś pierwszy wiersz. Pytanie, od czego zacząć.
[zielinski_dziwny] Przypominasz sobie drżącą rękę pana Zielińskiego. Ten sam staroświecki styl.

* Zanieś wiersz do biblioteki, do Maćka -> kronika_1
* Idź do pani Wandy, która ma klucze do wszystkiego -> wanda_1
* [!ola_razem] Poszukaj Oli w redakcji gazetki -> gazetka_1
* [ola_razem] Ola już czeka na ciebie - idźcie razem pod aulę -> aula_drzwi

## kronika_1
Maciek, zwany Profesorem, siedzi w bibliotece jak zawsze. Czyta wiersz i od razu sięga po kronikę szkoły z 1983 roku.

Na zdjęciu pięciu chłopaków z gitarami na scenie auli. Podpis: zespół Echo, przed studniówką. Następna strona jest wyrwana.

> ustaw: kronika

* Poproś Maćka, żeby poszukał wyrwanej strony -> kronika_2
* Pożycz kronikę bez pytania, kiedy Maciek się odwróci -> kronika_2 +kronika_zabrana
* [kuba_wie] Maciek już słyszał od Kuby - zapytaj, co sam o tym myśli -> kronika_2 +maciek_pomaga

## kronika_2
[kronika_zabrana] Kronika ciąży ci w plecaku. Maciek będzie wściekły, kiedy się zorientuje.
[maciek_pomaga] "To nie jest zwykły żart" - mówi Maciek. - "Ktoś chce, żeby ktoś coś znalazł. Wchodzę w to."

Na odwrocie zdjęcia imiona. Podkreślone dwa razy: "Janek Wrona - teksty". Obok: "Wojtek Zieliński - perkusja".

Ten chłopak pisał teksty. Tak jak ty. A perkusista uczy cię dziś polskiego.

* Idź z tym do pani Wandy -> wanda_1
* Idź prosto pod drzwi auli -> aula_drzwi

## wanda_1
Pani Wanda pracuje w tej szkole od trzydziestu lat. Pęk kluczy przy jej pasku dzwoni przy każdym kroku.

[kronika] Kiedy widzi kronikę pod twoją pachą, unosi brwi. "Echo" - mówi tylko. - "Dawno nikt o nich nie pytał."

* Zapytaj grzecznie o stary zegar -> wanda_2 +szacunek_wandy
* Poproś od razu o klucz do auli -> wanda_odmowa
* [kronika] Pokaż jej zdjęcie zespołu -> wanda_2 +szacunek_wandy +wanda_wspomina

## wanda_odmowa
Pani Wanda patrzy na ciebie chłodno. "Klucze są od pilnowania, nie od rozdawania" - mówi. - "Zwłaszcza tamten."

Odwraca się do swojej szafki z kluczami. Rozmowa skończona.

* Przeproś i zapytaj o zegar -> wanda_2
* Odejdź i spróbuj sam -> aula_drzwi

## wanda_2
"Ten zegar stanął tej samej nocy, kiedy zamknęli aulę" - mówi pani Wanda. - "Nikt go potem nie nakręcał. Mówią, że czeka."

[wanda_wspomina] Patrzy długo na zdjęcie. "Janek Wrona. Siadywał w mojej kanciapie i pisał. Taki jak ty, Wieszczu. Słowami umiał wszystko."

* Podziękuj jej -> aula_drzwi
* [szacunek_wandy] Zapytaj, czy mogłaby otworzyć aulę -> aula_drzwi +klucz

## gazetka_1
W redakcji "Dzwonka" Ola przykleja coś do ściany. Kiedy wchodzisz, szybko to zakrywa.

* Pokaż jej wiersz -> gazetka_2 +zaufanie_oli
* Zapytaj, co zakryła -> gazetka_2 +ola_unika

## gazetka_2
[ola_unika] Ola marszczy brwi. "Nie twoja sprawa" - mówi. Ale po chwili wzdycha i jednak ci pomaga.
[!ola_unika] Ola czyta wiersz dwa razy. Potem patrzy na ciebie inaczej niż zwykle.

Wyciąga z szafy stary numer "Dzwonka" z 1983 roku. Na pierwszej stronie: "Studniówka odwołana. Aula zamknięta do odwołania."

* Idźcie razem pod aulę -> aula_drzwi +ola_razem
* Idź sam - nie chcesz jej w to wciągać -> aula_drzwi

## aula_drzwi
Po lekcjach szkoła pustoszeje. Stoisz przed wielkimi drzwiami starej auli.

[ola_razem] Ola stoi obok ciebie. Słyszysz, jak szybko oddycha.
[klucz] W kieszeni ściskasz stary klucz od pani Wandy. "Ja nic nie wiem" - powiedziała, kiedy ci go dawała.
[dyrektor_nerwowy] Przypominasz sobie wzrok dyrektora uciekający do szuflady. Co on tam trzyma?

Drzwi są zamknięte od dwudziestu lat. A jednak zza nich dobiega cichy dźwięk. Tik. Tak. Tik.

* [klucz] Przekręć klucz -> aula
* [!klucz] Wejdź przez uchylone okienko na zapleczu sceny -> aula +zaplecze
* Zawróć - to nie twoja sprawa -> koniec_zamknieta

// --- Akt 2 - Sala pod zegarem ---

## aula
[zaplecze] Przeciskasz się przez okienko i zeskakujesz między stare dekoracje.
[klucz] Zamek zgrzyta, ale ustępuje.

W środku kurz, rzędy krzeseł i scena pod szarą kurtyną. Na ścianie wielki zegar. Wahadło kołysze się równo.

Ktoś go nakręcił. W skrzyni zegara, za wahadłem, leży zeszyt: "Teksty. J. Wrona".
[ola_razem, zaufanie_oli] Ola dotyka okładki i nagle odwraca wzrok.

Na korytarzu kroki. Światło latarki.

* Schowaj zeszyt pod kurtkę i wyjdź mu naprzeciw -> dyrektor_aula
* Odłóż zeszyt i schowaj się za kurtyną -> koniec_zamknieta
* [ola_razem] Daj Oli zeszyt - niech ucieka zapleczem -> dyrektor_aula +ola_uciekla

## dyrektor_aula
W drzwiach staje dyrektor Kowal. Patrzy na tykający zegar i blednie.
[ola_uciekla] Ola zdążyła zniknąć na zapleczu.
[kuba_wie] "Słyszałem, jak Kuba krzyczał o ukrytym słowie" - mówi.

"To ty piszesz te wiersze?" - pyta cicho.

* Powiedz, że nie ty - ktoś chce, żeby ta sala przemówiła -> szyfr
* Zapytaj, czego tak się boi -> szyfr +dyrektor_pytany
* [bartek_patrzy] Powiedz, że to pewnie Bartek - widziałeś, jak się gapił -> koniec_bartek
* [zielinski_dziwny] Weź wiersze na siebie, żeby chronić pana Zielińskiego -> koniec_autor
* [ola_razem] Weź wiersze na siebie, żeby chronić Olę -> koniec_autor

// --- Akt 3 - Szyfr i prawda ---

## szyfr
Dyrektor kazał ci tylko wyjść. Wieczorem otwierasz zeszyt Janka.
[ola_uciekla] Ola przyniosła go zdyszana pod twój blok.

| Świece zgasły i na scenie zapadł mrok,
| ktoś się śmiał, a potem było cicho.
| Ja wziąłem winę zamiast cudzych słów.
| Prawdę znajdzie ten, kto umie czytać od końca.
| Zostawiam ci tę piosenkę. Mnie już nie żal.

Na marginesie zegar ze wskazówkami narysowanymi wstecz.

* Przeczytaj pierwsze litery wersów, jak w pierwszym wierszu -> szyfr_zle +proba_pierwsze
* Przeczytaj ostatnie litery wersów -> prawda
* Przeczytaj piosenkę od końca, słowo po słowie -> szyfr_zle +proba_tyl

## szyfr_zle
[proba_pierwsze] Ś, K, J, P, Z. Nic z tego nie wychodzi.
[proba_tyl] Żal, już, nie, mnie, piosenkę... Same słowa, żadnej tajemnicy.

Patrzysz na zegar na marginesie. Wskazówki idą wstecz. Od końca... ale od końca czego?

* Spróbuj jeszcze raz -> szyfr -proba_pierwsze -proba_tyl

## prawda
K, O, W, A, L. Kowal.

Na ostatniej stronie Janek opisał tamtą noc: ktoś wygłupiał się na scenie i przewrócił sztandar szkoły na świece. Ten ktoś to dzisiejszy dyrektor. A Janek wziął winę na siebie.
[dyrektor_pytany] Teraz wiesz, czego bał się w auli.
[ola_razem, zaufanie_oli] Dzwoni Ola. "Janek Wrona to mój tata" - mówi cicho. - "Nigdy mi nie powiedział, dlaczego odszedł."

Do studniówki tydzień. Co zrobisz z prawdą?

* Porozmawiaj z dyrektorem w cztery oczy -> koniec_ballada
* Przeczytaj wszystko na głos na studniówce -> koniec_scena
* Oddaj zeszyt panu Zielińskiemu -> koniec_cicha
* [ola_razem] Daj zeszyt Oli - niech opisze to w "Dzwonku" -> koniec_dzwonek

// --- Zakończenia (tekst krótszy - pod nim tytuł i licznik zakończeń) ---

## koniec_ballada
Dyrektor długo milczy. Na studniówce sam wychodzi na scenę i mówi szkole prawdę o 1983 roku.

Zespół gra piosenkę Janka. Ostatnią zwrotkę dopisałeś ty.
[ola_razem, zaufanie_oli] W drzwiach auli staje siwy mężczyzna. Janek. Ola bierze cię za rękę.
[ola_razem, !zaufanie_oli] Ola co chwilę patrzy na drzwi, jakby na kogoś czekała.
[!ola_razem] Tylko drzwi auli zostają puste. Ktoś jeszcze powinien to usłyszeć.

> koniec: Ballada wraca

## koniec_scena
Na studniówce wchodzisz na scenę i czytasz piosenkę Janka. Potem mówisz, co w niej ukryto.

Sala milknie. Dyrektor wychodzi bez słowa. Prawda wyszła na jaw, ale bal już się nie klei.
[ola_razem] Ola nie jest pewna, czy tak było trzeba.

> koniec: Prawda na scenie

## koniec_cicha
Pan Zieliński długo czyta zeszyt. "To ja pisałem wiersze" - przyznaje. - "Grałem z Jankiem w Echu."

Tydzień później aula zostaje, a zespół gra na studniówce. Ale czy wiesz już wszystko?

> koniec: Cicha sprawiedliwość

## koniec_bartek
Dyrektor wzywa Bartka. Okazuje się, że Bartek kombinował tylko przy składce na studniówkę.

Wiersze się urywają, aula idzie do przebudowy. Kuba długo się do ciebie nie odzywa.

Rok później w twojej szafce leży nowy wiersz...

> koniec: Nie ten trop

## koniec_zamknieta
Aula zostaje zamknięta. Po studniówce robotnicy wynoszą z niej wszystko, razem ze starym zegarem.

Na balu grasz z Kubą nową piosenkę. O tym, czego już nie da się odzyskać.

> koniec: Zamknięta sala

## koniec_autor
Mówisz, że to ty pisałeś wiersze. Dyrektor zakazuje ci występu na studniówce.
[zielinski_dziwny] Pan Zieliński kiwa ci głową z daleka.
[ola_razem] Ola ściska twoją dłoń. Wie, kogo chronisz.

Na balu zespół gra twoją piosenkę. Wszyscy wiedzą, czyja jest. A zeszyt Janka czeka w szufladzie.

> koniec: Autor wierszy

## koniec_dzwonek
Ola publikuje w "Dzwonku" wszystko: piosenkę, szyfr i nazwisko dyrektora. Szkoła huczy.
[zaufanie_oli] Na studniówce Ola tańczy z tobą. "Napisaliśmy to razem" - mówi.
[!zaufanie_oli] Twoje nazwisko nie pada w artykule. Ola mija cię na korytarzu bez słowa.

> koniec: Na pierwszej stronie
