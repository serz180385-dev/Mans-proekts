
ParkNow — Viedās Autostāvvietas Pārvaldības Sistēma

ParkNow (SemVer Stable Release v1.3.0) ir pilna cikla (Fullstack) tīmekļa lietotne viedu autostāvvietu pārvaldībai un automatizācijai konceptā Smart City. Sistēma nodrošina interaktīvu stāvvietu vietu monitoringu, lietotāju virtuālo maku pārvaldību, automatizētu sesiju pagarināšanu un autonomu AI kameru emulāciju pārkāpumu fiksēšanai.
ParkNow (SemVer Stable Release v1.3.0) представляет собой Fullstack веб-приложение для управления и автоматизации умных парковочных пространств в концепции Smart City. Система обеспечивает интерактивный мониторинг парковочных мест, управление виртуальными кошельками водителей, автоматическое продление сессий и автономную эмуляцию ИИ-камер для фиксации нарушений.

🛠 Tehniskais steks

• Backend: Python 3.x, Flask Framework (Blueprint modular architecture)
• Frontend: HTML5, CSS3 (Flat UI, Neon UI accents, CSS Grid Layout), JavaScript (Interactive UX)
• Database: No-SQL JSON Storage / SQLite structure readiness schema
• Security & Testing: Bandit SAST Auditor, Regex Formatter, Secure Flask Sessions

📂 Projekta Struktūra

Кодовая база объёмом 1069 строк серверной логики спроектирована по принципу Separation of Concerns (Разделение ответственности) и разбита на следующие модули:
• app.py — Lietotnes sirds, Flask servera palaišana, globālo maršrutu apstrāde un kases integrācija.
• database.py — Datu bāzes kodols, No-SQL JSON failu lasīšana/rakstīšana un sesiju automātiskā pagarināšana.
• routes_driver.py — Vadītāja personīgais kabinets, reģistrācija un autorizācija ar Regex validāciju, maku papildināšana.
• routes_admin.py — Administratora panelis, meklēšana, lietotāju servera paginācija un finanšu analītika.
• routes_emulator.py — Aparatūras kameras emulators (vārtu iebraukšanas/izbraukšanas simulācija).
• templates/ — HTML skati (veidnes):
	• index.html — Interaktīvā stāvvietu karte vadītājiem (25 vietas).
	• admin.html — Dispečera vadības panelis.
	• login.html — Autentifikācijas un reģistrācijas forma ar tabiem.

⚙️ Funkcionalitāte


1. Autovadītāja modulis

• Interaktīvā Grid karte: 25 vietas ar stingru zonējumu: Invalīdu vietas (1-5 ♿), Regulārā zona (6-20), Elektroauto zona (21-25 ⚡).
• GDPR datu privātums: Vadītājs kartē redz tikai savas mašīnas numuru. Sveši numuri tiek maskēti ar uzrakstu "Aizņemts".
• Virtuālais maks: Balansa kontrole līdz centam (round(balance, 2)). Aizsardzība pret nepietiekamiem līdzekļiem.
• Regex validācija: Reģistrācija pārbauda tālruņus (+371...), e-pastus (@) un Latvijas auto numuru formātu (AA1234).

2. Administratora panelis un Finanšu kontrole

• Meklēšana un Paginācija: Ātra filtrēšana starp simtiem lietotāju, parādot strictly pa 5 vadītājiem lapā.
• Finanšu vidžeti: Reāllaika peļņas aprēķins ("Ieņēmumi no rezervācijām", "Iekasētie sodi", "Kopējie papildinājumi").
• Eksporta sistēma: Finanšu žurnāla darījumu vēstures tūlītēja lejupielāde .txt failā vienā klikšķī.
• Piespiedu evakuācija: Iespēja administratoram manuāli atbrīvot vietu ar aizsardzību caur JavaScript confirm.

3. Viesu uzskaites un Kombinēto sodu sistēma

• Dinamiskais parādu kalkulators: Sistēma fiksē nereģistrētus transportlīdzekļus (system), seko to stāvēšanas laikam un reālajā laikā rēķina parādu pēc tarifa 2.00 EUR/stundā.
• Kombinētais CSDD sods: Ja klients aizbrauc bez apmaksas vai administrators sastāda aktu manuāli, sistēma piemēro viedo sodu: 30.00 EUR fiksētā bāze + sakrājusies stundu maksa. Dati tiek automātiski sagatavoti nosūtīšanai uz CSDD, un vieta kartē tiek atbrīvota.

🔒 Drošība un SAST Audits 

Sistēma ParkNow ir veiksmīgi izgājusi drošības auditu un pilnībā aizsargāta pret galvenajiem OWASP Top 10 apdraudējumiem:
1. Broken Authentication aizsardzība: Paroļu drošība un divu faktoru sesiju izolācija pēc session['username'] novērš svešu maku līdzekļu tērēšanu.
2. Aparatūras aizsardzība (Hardware Exception Handling): AI kameras iebraukšanas routs pirms datu ierakstīšanas veic slota pārbaudi. Ja vieta nav brīva, iebraukšana tiek bloķēta, novēršot auto uzslāņošanos JSON datu bāzē.
3. SAST Bandit Audits: Statiskā koda analīze apstiprināja 0 kritisku biznesa loģikas ievainojamību visā Python pirmkodā.

🚀 Palaišana un Uzstādīšana

Lai lokāli palaistu projektu, izpildiet šādas darbības terminālī:
1. Klonējiet vai lejupielādējiet projekta mapi:bash
cd My_proekt

2. Pārliecinieties, ka ir uzstādīta bibliotēka Flask:bash
pip install flask

3. Palaidiet galveno servera moduli:bash
python app.py

4. Atveriet pārlūkprogrammu un pārejiet uz adresi:
http://127.0.0.1:5000

📊 SemVer Versiju Vēsture

• v0.1.0 – v0.8.0 — Sākotnējās konsoles skices, pāreja uz Flask tīmekļa dzinēju, pamata JSON shēmu izveide.
• v1.0.0 — Monolīta koda sadalīšana Blueprint moduļos, meklēšanas un paginācijas ieviešana administratora panelī.
• v1.1.0 — Nereģistrēto viesu uzskaites sistēmas un AI kameras dubultās iebraukšanas bloķēšanas aizsardzības integrācija.
• v1.2.0 — Bilances korekcijas routa optimizācija, pārcelšana uz app.py kodolu un viltus 404 kļūdu likvidēšana.
• v1.3.0 (Current Stable) — Kombinētā CSDD soda algoritma izstrāde (Bāze + Stundas), datu eksporta sistēmas iznese globālajā līmenī, pilnīga koda konservācija. Status: working tree clean.
