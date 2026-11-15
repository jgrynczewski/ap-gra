#!/usr/bin/env bash
# Aktualizacja prawdziwego Kompana (port 8768) bez utraty danych Radka.
# Procedura krok po kroku: KOMPAN_PLAN.md w repo AP, "Aktualizacja bez utraty danych".
# Instancji testowej nie dotyka. Uruchamiać, gdy Radek nie rozmawia z Kompanem.
set -euo pipefail

cd "$(dirname "$0")/.."
DANE=dane-kompan
KOPIE="$HOME/kopie-kompan"
HEALTH=http://localhost:8768/v1/kompan/health
USLUGA=ap-gra-kompan

stan() {  # "liczba notatek | tytuł ostatniej rozmowy | test"
    curl -sf "$HEALTH" | python3 -c '
import json, sys
h = json.load(sys.stdin)
print("%s | %s | %s" % (h["notatki"], (h["ostatnia"] or {}).get("tytul", "-"), h["test"]))'
}

przerwij() {
    echo
    echo "PRZERWANE: $1"
    echo "Uruchamiam Kompana z powrotem (stara wersja, dane nietknięte)."
    docker compose start "$USLUGA" || true
    exit 1
}

[ -d "$DANE" ] || { echo "Nie ma katalogu $DANE w $(pwd) - nic nie robię."; exit 1; }

read -r -p "Radek teraz nie rozmawia z Kompanem? [t/N] " ok
[ "$ok" = "t" ] || { echo "Nic nie zrobiłem."; exit 0; }

# 1. Stan przed aktualizacją
PRZED=$(stan) || { echo "Kompan nie odpowiada na porcie 8768. Uruchom go (docker compose up -d $USLUGA) i spróbuj jeszcze raz."; exit 1; }
case "$PRZED" in *"| True") echo "Port 8768 to instancja testowa?! Przerywam."; exit 1;; esac
echo "Przed: notatki | ostatnia rozmowa | test = $PRZED"

# 2. Zatrzymanie, żeby nic nie zapisywało się w trakcie kopii
docker compose stop "$USLUGA"

# 3. Kopia danych i sprawdzenie, że da się ją odczytać
mkdir -p "$KOPIE"
KOPIA="$KOPIE/dane-kompan-$(date +%F-%H%M).tgz"
sudo tar czf "$KOPIA" "$DANE" || przerwij "kopia się nie udała"
[ -s "$KOPIA" ] || przerwij "kopia jest pusta"
sudo tar tzf "$KOPIA" > /dev/null || przerwij "kopii nie da się odczytać"
echo "Kopia: $KOPIA ($(du -h "$KOPIA" | cut -f1))"

# 4. Nowy kod i nowy obraz
git pull --ff-only || przerwij "git pull się nie udał"
docker compose build || przerwij "budowanie się nie udało"
docker compose up -d

# 5. Czekanie, aż Kompan wstanie, i porównanie
PO=""
for _ in $(seq 60); do
    PO=$(stan 2>/dev/null) && break
    sleep 2
done
[ -n "$PO" ] || { echo "UWAGA: Kompan nie odpowiada po aktualizacji. Sprawdź: docker logs --tail 30 $USLUGA"; exit 1; }
echo "Po:    notatki | ostatnia rozmowa | test = $PO"

if [ "$PRZED" = "$PO" ]; then
    echo "OK: te same notatki i ta sama ostatnia rozmowa."
    echo "Teraz: cd ~/Assistive-Prototypes && git pull, potem AP od nowa."
else
    echo "UWAGA: stan się różni. Nie używajcie Kompana, dopóki tego nie sprawdzisz."
    echo "Przywrócenie kopii: KOMPAN_PLAN.md (AP), \"Aktualizacja bez utraty danych\"; kopia: $KOPIA"
    exit 1
fi
