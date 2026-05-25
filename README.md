# SCHED//PRO — Planer Proizvodnje

Lokalna aplikacija za optimizaciju i planiranje proizvodnih procesa u malim i srednjim radionicama. Razvijena u Python/Streamlit tehnologiji, radi potpuno offline bez potrebe za internetom ili serverima.

---

## TEHNIČKI PODACI

| Stavka | Vrednost |
|---|---|
| Platforma | Windows 10/11 (64-bit) |
| Baza podataka | SQLite (lokalni fajl `scheduler.db`) |
| Tehnologija | Python 3.12 + Streamlit + Pandas + Plotly |
| Pokretanje | `run.bat` (dvoklik) |
| Pristup | Browser: `http://localhost:8501` |
| Prijava | `admin` / `admin` |
| Veličina | ~410 MB (sa embedded Python-om) |

---

## STRUKTURA APLIKACIJE

Aplikacija je organizovana kroz 10 kartica (tabova) koje prate prirodan tok pripreme i realizacije proizvodnje:

### 1. RADNA MESTA
Definisanje radnih mesta (mašina, radnih stanica) i njihovih parametara:
- **Tip:** proizvodno / kontrola
- **H/dan:** radni sati po danu
- **Efikasnost:** % iskorišćenja
- **Maks. paralelno:** broj poslova koji mogu istovremeno da se rade

> Prvi korak — pre svega definisati radna mesta.

### 2. NALOZI ZA ISPORUKU
Unos narudžbina kupaca:
- Kupac, oznaka dela, količina, rok isporuke, prioritet
- Sistem automatski kreira **radni nalog** (proizvodni) sa svim operacijama iz tehnološkog šablona
- Ukoliko ne postoji šablon za datu oznaku dela, nalog se kreira bez radnog naloga — potrebno je definisati šablon

### 3. RADNI NALOZI (PROIZVODNJA)
Pregled svih proizvodnih radnih naloga:
- Svaki nalog sadrži tehnološki postupak (operacije na radnim mestima)
- Mogućnost štampe — preuzima se HTML fajl formatiran za štampu (sadrži: broj naloga, oznaku dela, količinu, rok, tabelu operacija, polje za potpis izvršioca)
- Editovanje statusa (neraspoređeno → raspoređeno → pušteno → u radu → završeno → otkazano)
- Crvenom bojom se označavaju poslovi koji kasne

### 4. TEHNOLOŠKI ŠABLONI
Definisanje rutiranja za svaku oznaku dela:
- Za svaku oznaku dela definišu se operacije (koraci)
- Svaka operacija: redni broj, radno mesto, priprema (h), obrada po komadu (h), opis
- Kada se kreira nalog za isporuku, operacije se automatski kopiraju iz šablona u radni nalog

> Preporuka: definisati šablone pre kreiranja naloga za isporuku.

### 5. GANT RASPORED
Vizuelni prikaz vremenskog rasporeda proizvodnje:
- Gantt grafikon — svaki posao ima svoju boju, operacije koje kontrolišu (kontrola) imaju šrafuru
- Metrike: broj konflikata, raspoređenih operacija, prekoračenja kapaciteta
- Tabela rasporeda sa vremenima početka i kraja
- Pomeranje poslova (šta-ako analiza) — izaberi posao i novi datum početka

> Pre pokretanja raspoređivača potrebno je da postoje radni nalozi sa operacijama.

### 6. KONFLIKTI I KAPACITET
Detekcija problema u rasporedu:
- **Preklapanje operacija:** prikazuje sve operacije koje se vremenski preklapaju na istom radnom mestu
- **Prekoračenje kapaciteta:** prikazuje dane kada je planirano više sati nego što radno mesto ima na raspolaganju

### 7. KALENDAR
Definisanje neradnih dana (praznici, zastoji):
- Dodavanje datuma sa opisom
- Raspoređivač automatski preskače neradne dane i vikende

### 8. ŠTA-AKO: HITAN POSAO
Simulacija ubacivanja hitnog posla u postojeći raspored:
- Unosi se oznaka dela, količina, rok i operacije
- Sistem kreira privremeni posao, raspoređuje ga i prikazuje uticaj na postojeće poslove
- Jednim klikom se svi simulirani poslovi brišu

### 9. CSV UVOZ
Grupni uvoz naloga za isporuku iz CSV fajla:
- Mogućnost preuzimanja šablona
- Automatski kreira radne naloge iz šablona (ako postoje)

### 10. ZALIHE
Praćenje materijala i stanja na lageru:
- Dodavanje stavki (oznaka dela, naziv, količina, jedinica, minimalna zaliha)
- Evidencija prometa (ulaz/izlaz sa referencom)
- Upozorenje kada zaliha padne ispod minimuma (crveno označavanje)

---

## ALGORITAM RASPOREĐIVANJA

Aplikacija podržava dva režima:

| Režim | Opis |
|---|---|
| **Napred (prioritet)** | Poslovi se raspoređuju od danas prema budućnosti. Prvo idu poslovi sa višim prioritetom i kraćim rokom. |
| **Nazad (od roka)** | Poslovi se raspoređuju unazad od roka isporuke. Korisno kada je rok fiksan i treba videti kada je najkasnije moguće početi. |

**Radno vreme:** 06:00 — 22:00 (subota i nedelja neradni dan)

---

## LICENCIRANJE

Aplikacija koristi offline licenciranje:
- **Trial period:** 30 dana
- **Upozorenje:** 14 dana pred istek prikazuje se podsetnik
- **Blokada:** nakon isteka trial perioda, aplikacija prikazuje samo ekran za unos licencnog ključa
- **Hardver ID:** jedinstveni identifikator računara (MAC adresa + ime računara + CPU)
- **Anti-tamper:** provera sistemskog vremena i hardverskih identifikatora pri svakom pokretanju

Za dobijanje licencnog ključa:
1. Pokrenite aplikaciju
2. Sa ekrana za licencu kopirajte Hardver ID
3. Pošaljite Hardver ID developeru
4. Dobijeni ključ unesite u polje i kliknite AKTIVIRAJ

---

## INSTALACIJA (OFFLINE)

### Opcija 1: Portable folder (preporučeno)
1. Kopiraj **SCHEDPRO** folder na USB stick
2. Prenesi na ciljni računar
3. Dvoklik na `run.bat`
4. Sačekaj 10-15 sekundi da se server pokrene
5. Browser se otvara automatski na `http://localhost:8501`

### Opcija 2: ZIP arhiva
1. Raspakuj `SCHEDPRO_v1.0.zip`
2. Dvoklik na `run.bat` iz raspakovanog foldera

### Zaustavljanje
- Zatvori prozor `run.bat` (CMD prozor)
- Ili pritisni `Ctrl+C` u CMD prozoru

---

## PODACI

Svi podaci se čuvaju u fajlu `app/scheduler.db`.
- **Backup:** kopiraj ovaj fajl na sigurno mesto
- **Reset:** obriši ovaj fajl — aplikacija će kreirati novi sa default nalogom

---

## RAZVOJ

### Pokretanje iz izvornog koda
```
pip install -r requirements.txt
python app.py
```

### Struktura fajlova
```
SCHEDPRO/
├── app.py              # Streamlit UI (glavna aplikacija)
├── models.py           # SQLite modeli i DB helper
├── scheduler.py        # Algoritmi raspoređivanja
├── license.py          # Offline licenciranje
├── generate_key.py     # Admin alat za generisanje ključeva
├── build_portable.ps1  # Build script za portable verziju
├── requirements.txt    # Python dependency
└── scheduler.db        # SQLite baza podataka
```

### Izgradnja portable verzije
```
.\build_portable.ps1
```

---

## MAPA PUTA

- [x] Radna mesta
- [x] Radni nalozi sa operacijama
- [x] Nalozi za isporuku
- [x] Tehnološki šabloni
- [x] Gantt grafikon
- [x] Detekcija konflikata i kapaciteta
- [x] Šta-ako simulacija hitnih poslova
- [x] CSV uvoz
- [x] Štampa radnih naloga
- [x] Zalihe (inventory)
- [x] Offline licenciranje sa anti-tamper zaštitom
- [ ] Android aplikacija (dugoročni plan)

---

*SCHED//PRO v1.0 — © 2026*
