# Propozycja: „Ostatnia zwrotka” jako przygodówka z grafiką

**Status: propozycja do sprawdzenia, odłożona.** Research zrobiony 2026-11-06. Nic z tego nie jest zbudowane ani zdecydowane - użytkownik chce kiedyś do tego wrócić. Obecna gra tekstowa zostaje bez zmian, z prostą animacją `NightScene` w AP (decyzja 2026-11-05).

**Pomysł:** zamiast tekstu i opcji - gra z grafiką, w której bohater chodzi po lokacjach, słychać odgłosy, a animacja jest w miarę atrakcyjna.

**Wniosek:** to wykonalne, ale nie samym kodem. Claude nie narysuje porządnej grafiki (próbka SVG i obecna scenka to pokazały) - obrazy musi tworzyć model obrazu, a Claude robi grę, animację i składanie całości. Nie wiadomo, czy efekt będzie atrakcyjny, więc **pierwszym krokiem jest prototyp jednej lokacji**.

> Przed powrotem do tematu sprawdzić ponownie modele, narzędzia i licencje - ta dziedzina szybko się zmienia.

## Wymagania użytkownika

- **Postacie bez widocznych twarzy** (od tyłu, w sylwetce). Gracz ma się utożsamić z ilustracją; przy wyraźnej twarzy „widać, że to nie on”.
- Sterowanie jednym przyciskiem, przez skanowanie jak w całym AP.
- Odgłosy i ruch na ekranie, nie tylko napisy.
- Bez prawdziwych osób z życia użytkownika (postacie są wymyślone).

## Wyniki researchu

Większość źródeł o grafice AI to blogi firm sprzedających te narzędzia - traktować orientacyjnie.

### Silnik
- **Godot + Popochiu** (wtyczka do przygodówek) - najlepiej pasuje. Najnowsza wersja to podobno 2.1.0 dla Godota 4.6, ale znalezione tylko na mirrorze repozytorium - potwierdzić na oficjalnym GitHubie (`carenalgas/popochiu`).
- **Adventure Game Studio** - alternatywa: licencja Artistic 2.0, ma wersję na Linuksa.
- **Escoria** (Godot) - znaleziona wersja jest stara (Godot 3), odpada na start.

### Grafika
- **Tła** - najłatwiejsza część. Spójny styl osiąga się, podając wcześniejsze obrazy jako wzór; postprodukcja nadal się przydaje.
- **Modele** - najczęściej polecane do spójności: Nano Banana Pro i Flux 2. GPT Image 2 przyjmuje dużo obrazów-wzorów, ale ma mało niezależnych testów. Żaden model nie jest w pełni spójny - sprawdzić na własnych postaciach.
- **Animacja postaci** - największy problem. Według jednego poradnika żadne narzędzie nie tworzy niezawodnie spójnych animacji w wysokiej rozdzielczości: zmieniają się proporcje, kolory, dodatki i grubość konturu. Zalecane: AI robi postać, animacja osobno.
- **Pixel art** - tu narzędzia radzą sobie najlepiej (np. PixelLab, Sorceress).
- **Godot** ma wbudowaną animację szkieletową 2D (`Polygon2D` + `Bone2D`), bez dodatkowych programów.

### Dźwięk
Najmniejszy problem. Licencje sprawdzić przed rozpowszechnianiem gry.
- **Sonniss GDC** - darmowe paczki co roku; starsze licencje: bez opłat i bez podawania autora. Tekstu licencji 2026 nie znalazłem.
- **Freesound** - licencja osobna dla każdego pliku; filtrować CC0.
- **ElevenLabs** - generator efektów; darmowy plan wymaga podania źródła, płatny nie.
- **Suno** - muzyka; darmowy plan tylko niekomercyjnie, płatny daje prawa komercyjne (własność utworów - źródła się różnią).

### Komputer AP (Ubuntu 20.04, Dell Latitude 7490)
- Tryb Compatibility Godota wymaga OpenGL 3.3. Karta Intel powinna to spełniać, ale model karty i sterownik trzeba sprawdzić na miejscu (`glxinfo`).
- Godot powinien działać na Ubuntu 20.04 (glibc 2.31 - informacja z forum), zgodności wersji 4.6 nie potwierdziłem. **Sprawdzić uruchomieniem na tym laptopie.**

### Sterowanie jednym przyciskiem
Nie znalazłem gotowego rozwiązania dla przygodówki. Zwykłe skanowanie punktowe całego ekranu jest wolne, a narzędzia systemowe często widzą grę jako jeden duży obszar - skanowanie trzeba wbudować w grę.

## Propozycje projektowe (moje, nie z researchu)

### Sterowanie
Gra podświetla kolejno miejsca i osoby na ekranie, a narrator je czyta (ten sam mechanizm i pauza co w `Board`). Po wyborze bohater sam tam idzie i wykonuje czynność. Chodzenie zostaje, ale bez sterowania kursorem.

### Styl grafiki

| Styl | Zalety | Wady |
|---|---|---|
| **Malowane tła + sylwetki postaci (rekomendacja)** | brak twarzy, łatwa spójność, ruch można zaprogramować | mniej mimiki, sceny o zmierzchu lub w nocy |
| Pixel art | najlepsze narzędzia do chodzenia | wygląd retro, mniej nastrojowy |
| Malowane postacie z ruchomymi częściami | najbogatszy wygląd | dzielenie postaci na części, ręczne dopracowanie ruchu |
| Żywe ilustracje bez chodzenia | najtaniej | to nie przygodówka |

Sylwetki: Ninę rozpoznać po włosach i sukience, Bigosa po kształcie. Ruch nadają światło lampionów, woda, świetliki i dźwięki otoczenia.

### Pozostałe pomysły
- **Prawdziwa piosenka w finale:** nagrane osobno warianty zwrotek łączone według wyborów gracza. Dodałoby dużo klimatu; wymaga osobnego sprawdzenia (czy fragmenty da się spójnie połączyć).
- **Podział pracy z modelem obrazu:** z kluczem API Claude generuje i wstępnie odsiewa obrazy. Ruch może oceniać tylko na podstawie klatek - o płynności i wrażeniu decyduje użytkownik.
- **Uruchamianie z AP (do sprawdzenia):** gra jako osobny proces na pełnym ekranie, start z planszy gier, a przycisk trafia do gry jako kliknięcie. Mogą zostać nagrania narratora Piper.

## Prototyp - pierwszy krok

**Zakres:** ogród z basenem, bohater, Nina i Bigos, 3-4 miejsca do wyboru, dźwięki, skanowanie jednym przyciskiem, styl sylwetek.

**Ma odpowiedzieć na trzy pytania:**
1. Czy podoba się użytkownikowi?
2. Czy działa płynnie na laptopie AP?
3. Czy dobrze się w to gra przyciskiem?

**Szacunki (moje, niepewne):** prototyp 1-2 dni; cała gra (około 7 lokacji) raczej kilka tygodni, głównie na produkcję grafiki.

**Do rozstrzygnięcia przy powrocie:**
- dostęp do modelu obrazu: klucz API albo obrazy wygenerowane przez użytkownika według promptów;
- styl: sylwetki czy inny;
- czy gra będzie kiedyś rozpowszechniana (od tego zależą licencje).

## Prompt do obrazu (pierwsza wersja)

Scena: nocny ogród willi. Rozmiar kwadratowy (najłatwiej przyciąć do panelu ~6:5) albo poziomy. W tej wersji postacie są od tyłu, nie w sylwetce - do dostosowania, jeśli wygra styl sylwetek.

```
A warm, cozy storybook illustration of a summer night in the garden of an old two-story villa. Seen from behind and slightly above, a young man and a young woman sit side by side on the edge of a softly glowing turquoise swimming pool, their feet in the water, small ripples around their ankles. Both are shown only from the back, no faces visible: he wears a simple blue t-shirt and has short dark hair; she wears a raspberry-pink summer dress and has long chestnut hair, and she gently leans her head on his shoulder. A small brown mixed-breed dog with a red collar sits on the pool deck next to them, tail up, looking at the villa.

Behind them stands an old villa with a balcony, columns at the entrance and a tiled roof; several windows glow with warm golden light, the front door is open and spills light onto a garden path. A garland of colorful paper lanterns (red, yellow, mint, blue, orange, purple) hangs across the garden, their reflections shimmering in the pool. Above: a deep navy-to-violet night sky full of stars and a bright full moon with a soft halo; dark cypress trees and gentle hills on the horizon; a few fireflies glowing above the grass.

Style: soft painterly digital illustration, gentle lighting, rich but calm colors, romantic and slightly humorous mood, like a cover of a modern illustrated novel. No text, no letters, no logos, no visible faces.
```

Samo tło pod animację - dopisać na końcu:

```
Empty scene version: no people, no dog, no lanterns, no fireflies - only the villa with lit windows, the pool, the garden and the night sky.
```

## Źródła

- **Silnik:** [Popochiu (mirror)](https://gh.r-mj.com/carenalgas/popochiu), [AGS - FAQ](https://www.adventuregamestudio.co.uk/site/ags/faq/), [AGS - repozytorium](https://github.com/romatthe/ags), [Escoria](https://github.com/godotengine/escoria)
- **Godot:** [wymagania systemowe](https://docs.godotengine.org/fr/4.3/about/system_requirements.html), [budowanie na Linuksa](https://docs.godotengine.org/de/4.5/engine_details/development/compiling/compiling_for_linuxbsd.html), [glibc - forum](https://forum.godotengine.org/t/dotnet-godot-4-games-require-glibc-versions-beyond-what-my-still-supported-linux-handles/45244), [szkielety 2D](https://docs.godotengine.org/en/4.4/tutorials/animation/2d_skeletons.html)
- **Grafika:** [sprite'y i animacja](https://abratabia.com/ai-game-art/ai-sprite-sheets.php), [spójność postaci - test](https://tech-insider.org/consistent-ai-character-generator-test-2026/), [porównanie modeli](https://techstackups.com/comparisons/gemini-vs-openai-vs-flux-vs-runway-character-consistency-may-2026/), [Scenario - przygodówki](https://scenario.com/post/designing-point-and-click-game-assets-with-scenario), [generowanie sprite'ów](https://sorceress.games/blog/sprawl-an-ai-sprite-animation-generator-walk-pack-2026)
- **Dźwięk:** [ElevenLabs](https://elevenlabs.io/sound-effects/commercial), [Sonniss 2026](https://rekkerd.org/sonniss-releases-gdc-2026-game-audio-bundle/), [licencje Freesound](https://licenseorg.com/guide/music-audio/freesound), [Suno - prawa](https://help.suno.com/en/categories/550145-ownership)
- **Sterowanie jednym przyciskiem:** [OneSwitch](https://oneswitch.org.uk/page/oneswitch-adventure), [badanie dostępności gier](https://par.nsf.gov/servlets/purl/10359093)
