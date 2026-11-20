# MetroMap Live (demo)

Browserversie van de print: dezelfde 82 LEDs op dezelfde plek, gevoed met de live
posities van de GVB-metro's. Draait op pc en telefoon.

## Starten

Op Windows: dubbelklik `software/demo/start-metromap.bat`. Die start de server en opent de pagina.

Of vanuit een terminal:

```sh
python3 software/demo/server.py
```

Open daarna `http://localhost:8000` op je pc, of het adres dat het script toont op je
telefoon (zelfde wifi). Alleen de Python-standaardbibliotheek is nodig.

De server is nodig omdat OVapi geen CORS-header meestuurt (de browser mag de data
niet rechtstreeks ophalen) en het HTTPS-certificaat van `v0.ovapi.nl` niet klopt.
De server haalt de data via `http://v0.ovapi.nl` op (gzip, ongeveer 16 kB per update in plaats van 340 kB) en cachet die 10 seconden.

## Hoe het werkt

1. `/line/GVB_5x_y` levert per lijn de haltes (timing points).
2. `/tpc/<alle haltes>` levert per halte de eerstvolgende passages, met verwachte
   aankomst- en vertrektijd per rit. Elke 15 seconden.
3. De passages worden per rit gegroepeerd. Een metro staat op de eerste halte die hij
   nog niet verlaten heeft: vol licht als hij er staat, gedimd en pulserend als hij
   er naartoe rijdt.
4. Elk station heeft twee LEDs, één per rijrichting: de LED rechts van de rijrichting
   hoort bij die richting.

Minder haltes opvragen maakt het niet kleiner: OVapi geeft per `/tpc`-aanvraag maximaal 300
passages terug, verdeeld over de gevraagde haltes. Met minder haltes krijg je alleen een
langer tijdvenster per halte. Daarom worden steeds alle haltes opgevraagd.

`/line/.../Actuals` is niet bruikbaar: voor de GVB-metro staan daar vrijwel alleen
ritten die nog moeten vertrekken.

De tijden zijn de verwachte tijden van GVB. Waar geen realtime data is, zijn dat de
dienstregelingstijden, dus een positie kan een halte afwijken bij vertraging.

## Bestanden

| Bestand | Wat |
|---|---|
| `metromap-live.html` | De gebouwde pagina (niet met de hand aanpassen) |
| `src/template.html` | Pagina, stationstabel en LED-koppeling |
| `tools/build.py` | Leest `hardware/metromap.kicad_pcb` en bouwt de pagina |
| `server.py` | Lokale server en doorgeefluik naar OVapi |

Na een wijziging aan de print of het template: `python3 software/demo/tools/build.py`.

De LED-nummers in de pagina zijn de posities in de dataketen (0 = eerste LED na
`DATA_IN`), dezelfde nummering die de firmware gebruikt.
