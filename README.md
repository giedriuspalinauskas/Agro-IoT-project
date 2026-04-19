# Agro IoT project
 Agro‑IoT web platforma
1. Projekto aprašymas
Šio projekto tikslas – sukurti web pagrindu veikiančią Agro‑IoT duomenų stebėjimo platformą, skirtą žemės ūkio objektų ir IoT įrenginių duomenų valdymui.
Sistema skirta autentifikuotiems vartotojams ir leidžia administruoti žemės vietas (sklypus), jų adresus bei prie jų prijungtus matavimo įrenginius.

2. Naudojamos technologijos
Front‑end

HTML5
JavaScript (be framework’ų pradiniame etape)
CSS (nebūtina pradžioje)

Back‑end

Python
Rekomenduojama naudoti:

FastAPI arba Flask (REST API)


Autentifikacija: sesijų arba JWT pagrindu

Duomenų bazė

PostgreSQL arba SQLite (pradiniam etapui)
ORM: SQLAlchemy (rekomenduojama)


3. Vartotojų rolės
Sistema turi palaikyti skirtingus vartotojų lygius:
3.1 Administratorius
Administratorius gali:

Matyti visus sistemos duomenis
Kurti, redaguoti ir šalinti:

vartotojus
žemės vietas
įrenginius


Priskirti vartotojus prie konkrečių žemės vietų

3.2 Paprastas vartotojas
Paprastas vartotojas gali:

Prisijungti prie sistemos
Matyti tik jam priskirtas žemės vietas
Peržiūrėti prie vietų prijungtų įrenginių duomenis
Negali kurti ar šalinti kitų vartotojų


4. Funkciniai reikalavimai
4.1 Autentifikacija

Visi svetainės duomenys prieinami tik prisijungusiems vartotojams
Privalomas:

prisijungimo (login) puslapis
atsijungimo (logout) funkcionalumas



4.2 Žemės vietų valdymas
Sistema turi leisti:

Sukurti žemės vietą su šiais laukais:

pavadinimas
adresas
aprašymas (nebūtinas)


Redaguoti ir šalinti žemės vietas (tik administratoriams)

4.3 Įrenginių valdymas
Kiekvienai žemės vietai galima:

Pridėti vieną ar daugiau IoT įrenginių
Įrenginys turi turėti:

pavadinimą
tipą (pvz. temperatūros, drėgmės, dirvožemio jutiklis)
unikalų identifikatorių


Ateityje įrenginiai teiks matavimo duomenis per API


5. Sistemos architektūra
Naršyklė (HTML + JS)
        ↓
REST API (Python – FastAPI / Flask)
        ↓
Duomenų bazė (PostgreSQL / SQLite)


Front‑end komunikuoja su back‑end per REST API
Back‑end atsakingas už:

vartotojų autentifikaciją
teisių tikrinimą
duomenų saugojimą




6. Ne-funkciniai reikalavimai

Sistema turi veikti Docker aplinkoje
Kodas turi būti tvarkingai struktūruotas
API turi grąžinti duomenis JSON formatu
Sprendimas turi būti tinkamas akademiniam baigiamajam darbui


7. Vystymo etapai (rekomenduojama)

Prisijungimo sistema
Vartotojų rolių realizavimas
Žemės vietų CRUD funkcionalumas
Įrenginių priskyrimas prie vietų
Duomenų atvaizdavimas web sąsajoje


8. Projekto paskirtis
Projektas kuriamas Agro‑IoT duomenų surinkimo ir analizės sistemos prototipui, skirtam naudoti studijų baigiamajame darbe.
