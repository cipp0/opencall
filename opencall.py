#!/usr/bin/env python3
"""Open call per artisti elettronica / audiovisivo / installazioni / luce.

  python3 opencall.py           scarica le call, aggiorna opencall.html e lo apre
  python3 opencall.py --telegram   come sopra, poi manda le nuove call sul bot Telegram (config.ini)
"""
import configparser, html, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request, webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (opencall personal scraper)"

DISC = re.compile(r"\b(sound|audio|music|musik|musician|composer|kompon|electronic|elektron|audiovisu|audio-visu|experimental|installation|light art|lichtkunst|light design|lighting design|media art|new media|medienkunst|digital art|digitale kunst|immersive|visual|digital|video|videokunst|video mapping|projection mapping|multimedia|transmedia|cross-?media|interaction design|interactive|interaktiv|hci|human[- ]computer|physical computing|creative coding|creative technolog|generative|klang|spatial|ambisonic|sonic|art (and|&) technology|arts? (and|&) science|art[- ]science|s\+t\+arts|xr|virtual reality|augmented reality|vr)", re.I)
# escluse se il titolo parla di queste discipline (nel testo possono comparire anche in call multidisciplinari)
OFF = re.compile(r"ceramic|keramik|porcelain|porzellan|pottery|painting|painter|malerei|\bmaler", re.I)
# ponytail: classificazione a parole chiave, sbaglia sui testi ambigui. Correggere le regex quando si vede un errore.
NOPAY = re.compile(r"\b(no|without|free of)\s+(application\s+|entry\s+|submission\s+|participation\s+)?(fees?|charges?)\b|free of charge|kostenlos|gebührenfrei|keine (teilnahme|einreich)gebühr", re.I)
PAY = re.compile(r"application fee|entry fee|submission fee|participation fee|registration fee|residency fee|paid by artist|teilnahmegebühr|einreichgebühr|anmeldegebühr", re.I)
FUND = re.compile(r"honorari|stipend|artist fee|\bgrants?\b|per diem|travel (costs|expenses)|production (budget|costs|support)|budget (of|is available)|fully funded|paid residency|prize money|preisgeld|dotiert|honorar|reisekosten", re.I)
MONEY = re.compile(r"€\s?\d|\d[\d.,]*\s?(€|eur\b|euro)", re.I)  # una cifra da sola può anche essere la quota da pagare

SPATIAL = re.compile(r"ambisonic|spatial (audio|sound|music)|spatiali[sz]|3d[ -]?(audio|sound)|binaural|multi-?channel|wave ?field|\bwfs\b|dolby atmos|surround sound|sound ?dome|klangdom|loudspeaker (array|orchestra)|acousmonium|immersive (audio|sound)|raumklang|mehrkanal", re.I)
CLOSED = re.compile(r"\b(call|applications?|submissions?|registrations?|entries)\s+(is\s+|are\s+|has\s+|have\s+)?(now\s+)?(been\s+)?closed\b"
                    r"|this call (is|has) (now )?(closed|ended|expired)|no longer accepting|deadline has passed"
                    r"|(bewerbungs|einreich)frist ist abgelaufen|ausschreibung ist (beendet|abgeschlossen|geschlossen)|bando (è )?(chiuso|scaduto)", re.I)
CLOSED_TITLE = re.compile(r"\bclosed\b|abgelaufen|\bchiuso\b|scaduto", re.I)
AT = re.compile(r"austria|österreich|\bwien\b|vienna|graz|\blinz\b|salzburg|innsbruck|klagenfurt|st\.? pölten|bregenz|eisenstadt", re.I)
EU = re.compile(r"albania|andorra|armenia|belgi|bosnia|bulgari|croatia|kroatien|cyprus|zypern|czech|tschech|denmark|dänemark|estonia|estland|finland|finnland|france|frankreich|georgia|german|deutschland|greece|griechenland|hungary|ungarn|iceland|island|ireland|irland|italy|italien|kosovo|latvia|lettland|liechtenstein|lithuania|litauen|luxemb|malta|moldova|monaco|montenegro|netherlands|niederlande|holland|macedonia|norway|norwegen|poland|polen|portugal|romania|rumänien|serbia|serbien|slovakia|slowakei|slovenia|slowenien|spain|spanien|sweden|schweden|switzerland|schweiz|ukrain|united kingdom|\buk\b|england|scotland|wales|türkiye|turkey|türkei|europe|europa|berlin|hamburg|münchen|munich|cologne|köln|leipzig|paris|lyon|marseille|amsterdam|rotterdam|brussels|bruxelles|antwerp|barcelona|madrid|lisbon|lisboa|porto|milan|milano|rome|roma|turin|torino|venice|venezia|prague|praha|warsaw|kraków|krakow|ljubljana|zagreb|budapest|bratislava|london|glasgow|dublin|copenhagen|stockholm|oslo|helsinki|athens|bucharest|sofia|zürich|zurich|geneva|basel|riga|tallinn|vilnius|belgrade|beograd", re.I)

MONTHS = {m: i + 1 for i, ms in enumerate(["jan gen", "feb", "mar mär", "apr", "may mai mag", "jun giu", "jul lug", "aug ago", "sep set", "oct okt ott", "nov", "dec dez dic"]) for m in ms.split()}
MON = r"\b(" + "|".join(MONTHS) + ")"  # solo nomi di mese veri, così "2026 MUSLAB" non diventa "26 mus"


def get(url):
    time.sleep(1)  # gentilezza verso i siti
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def text(h):
    h = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def find_deadline(t):
    """Prima data dopo 'deadline/closes/frist/bis/scadenza…'. ISO o ''."""
    for m in re.finditer(r"(deadline|closes?|closing|frist|einsendeschluss|bewerbungsschluss|einreichschluss|anmeldeschluss|until|bis zum|bis|by|scadenza|entro il|entro)\W{0,3}(.{0,50})", t, re.I):
        s = m.group(2)
        if d := re.search(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})", s):
            dd, mm, yy = map(int, d.groups())
        elif d := re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\.?\s+{MON}[a-zä]*\.?,?\s+(\d{{4}})", s, re.I):
            dd, mm, yy = int(d[1]), MONTHS.get(d[2].lower()), int(d[3])
        elif d := re.search(rf"{MON}[a-zä]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", s, re.I):
            dd, mm, yy = int(d[2]), MONTHS.get(d[1].lower()), int(d[3])
        else:
            continue
        try:
            return date(yy, mm, dd).isoformat()
        except (TypeError, ValueError):
            continue
    return ""


def funding(t, default="non funded"):
    t = NOPAY.sub("", t)
    if FUND.search(t):  # finanziata anche se chiede una piccola quota d'iscrizione
        return "funded"
    if PAY.search(t):
        return "a pagamento"
    return "funded" if MONEY.search(t) else default


def region(hint, t, default):
    for s in (hint, t):
        if AT.search(s):
            return "Austria"
        if EU.search(s):
            return "Europa"
    return default


# --- sorgenti: ogni funzione restituisce dict con url, title, source, country, deadline, [text]

def on_the_move():
    out = []
    for page in range(10):
        h = get(f"https://on-the-move.org/news?page={page}")
        cards = re.findall(r"<li class=\"list m-flex-nowrap\">(.*?)class='list-link'", h, re.S)
        for c in cards:
            title = html.unescape(re.search(r"<span class='block-title'>(.*?)</span>", c, re.S)[1])
            dl = re.search(r'datetime="(\d{4}-\d\d-\d\d)', c)
            out.append(dict(url="https://on-the-move.org" + re.search(r"href='([^']+)'", c)[1], title=title, source="On the Move",
                            country=(re.findall(r"\(([^()]+)\)\s*$", title) or [""])[0], deadline=dl[1] if dl else ""))
        if not cards or f"?page={page + 1}" not in h:
            break
    return out


def transartists_air():
    h = get("https://www.transartists.org/en/deadlines")
    return [dict(url="https://www.transartists.org" + u, title=html.unescape(t), source="TransArtists", country=c, deadline="")
            for u, t, c in re.findall(r'<h3><a href="(/en/air/[^"]+)"[^>]*>(.*?)</a>\s*\(([^)]*)\)</h3>', h)]


def transartists_board():
    h = get("https://www.transartists.org/en/call-artists")
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", h, re.S):
        title, links = re.search(r"<h2>(.*?)</h2>", row, re.S), re.findall(r'href="(https?://[^"]+)"', row)
        if title and links:
            t = text(row)
            out.append(dict(url=links[0], title=html.unescape(text(title[1])), source="TransArtists board", country="",
                            deadline=find_deadline(t), text=t))
    return out


def mica():
    posts = json.loads(get("https://www.musicaustria.at/wp-json/wp/v2/posts?categories=145&per_page=40&_fields=link,title,content"))
    out = []
    for p in posts:
        t = text(p["content"]["rendered"])
        out.append(dict(url=p["link"], title=html.unescape(p["title"]["rendered"]), source="mica", country="",
                        deadline=find_deadline(t), text=t))
    return out


# siti WordPress: si leggono i post degli ultimi 4 mesi con "open call"/"Ausschreibung"/"bando" nel titolo.
# Per aggiungerne uno basta una riga.
WP_SITES = ["starts.eu", "re-imagine-europe.eu", "www.v2.nl", "www.kupf.at", "www.musicboard-berlin.de", "www.musicexport.at",
            "www.aimi-musica.org"]
CALL = re.compile(r"open call|call for|\bcalls?\b|ausschreibung|stipendi|apply now|jetzt bewerben|bewerbung|bando|concorso", re.I)


def wp_posts(host, query):
    # ?rest_route= funziona su ogni WordPress, anche senza permalink "belli" (es. AIMI)
    return json.loads(get(f"https://{host}/?rest_route=/wp/v2/posts&{query}&_fields=link,title,content"))


def wordpress():
    since = (date.today() - timedelta(days=120)).isoformat()
    out = []
    for site in WP_SITES:
        try:
            posts = wp_posts(site, f"after={since}T00:00:00&per_page=50")
        except Exception as e:
            print(f"! {site}: {e}", file=sys.stderr)
            continue
        for p in posts:
            title = html.unescape(p["title"]["rendered"])
            if CALL.search(title):
                t = text(p["content"]["rendered"])
                out.append(dict(url=p["link"], title=title, source=site.removeprefix("www."), country="", deadline="", text=t))
    return out


def sounding_future():
    h = get("https://soundingfuture.com/whats-on?categories=open-call&limit=60")
    out = {}
    for card in h.split('class="grid md:grid-cols-[200px_1fr]')[1:]:  # ogni call compare due volte (layout mobile e desktop)
        a = re.search(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)<svg', card, re.S)
        if a and ">Open Call<" in card:
            country = re.search(r'tracking-widest">([^<:]+)</div>', card)
            out[a[1]] = dict(url=html.unescape(a[1]), title=html.unescape(text(a[2])), source="Sounding Future",
                             country=country[1].strip() if country else "", deadline="", text=text(card))
    return list(out.values())


SOURCES = [on_the_move, transartists_air, transartists_board, mica, wordpress, sounding_future]
AT_SOURCES = {"mica", "kupf.at", "musicexport.at"}  # portali austriaci: se il testo non dice altro, la call è in Austria
# testo della pagina di dettaglio: si taglia prima delle sidebar ("altre call") che falserebbero la classificazione
CUT = re.compile(r"Share this call|Latest news|Contact information|DutchCu\|ture")


def detail(url):
    u = urllib.parse.urlparse(url)
    if u.netloc in ("www.musicaustria.at", *WP_SITES):  # WordPress: solo il testo dell'articolo, senza menu e footer
        post_id = urllib.parse.parse_qs(u.query).get("p")  # link tipo ?p=4153
        posts = wp_posts(u.netloc, f"include={post_id[0]}" if post_id else f"slug={u.path.rstrip('/').rsplit('/', 1)[-1]}")
        if posts:
            return text(posts[0]["content"]["rendered"])
    h = get(url)
    t = text(h[max(h.find("<main"), 0):])
    return CUT.split(t)[0]


RULES = 4  # da aumentare quando si cambiano le regex: al giro dopo le call aperte già salvate vengono riclassificate


def classify(title, t, source, country, deadline=""):
    full = f"{title} {t}"
    return dict(
        deadline=deadline or find_deadline(t),
        closed=int(bool(CLOSED.search(t) or CLOSED_TITLE.search(title))),
        funding=funding(full, "funded" if source == "On the Move" else "non funded"),  # On the Move pubblica solo call che coprono almeno parte dei costi
        region=region(country or title, t, "Austria" if source in AT_SOURCES else "Mondo"),
        spatial=int(bool(SPATIAL.search(full))),
        relevant=int(bool(DISC.search(full)) and not OFF.search(title)),  # le non pertinenti restano nel db per non riscaricarle
        rev=RULES)


def scrape(db):
    today = date.today().isoformat()
    # si ricontrollano le call aperte classificate con regole vecchie e, ogni giorno, quelle senza scadenza nota
    # (la pagina può aver aggiunto la data o scritto "call closed")
    old = db.execute("SELECT url, title, source, country, deadline FROM calls WHERE relevant IS NOT 0 AND COALESCE(closed, 0)=0 "
                     "AND (((rev IS NULL OR rev<?) AND deadline>=?) OR (deadline='' AND first_seen>=?))",
                     (RULES, today, (date.today() - timedelta(days=60)).isoformat())).fetchall()
    for url, title, source, country, deadline in old:
        try:
            t = detail(url)
        except Exception:
            continue  # si riprova al prossimo giro
        db.execute("UPDATE calls SET deadline=:deadline, closed=:closed, funding=:funding, region=:region, spatial=:spatial, "
                   "relevant=:relevant, rev=:rev WHERE url=:url", dict(classify(title, t, source, country, deadline), url=url))
    db.commit()
    if old:
        print(f"ricontrollate {len(old)} call già salvate")
    known = {u for (u,) in db.execute("SELECT url FROM calls")}
    for src in SOURCES:
        try:
            items = src()
        except Exception as e:  # una sorgente rotta non deve bloccare le altre
            print(f"! {src.__name__}: {e}", file=sys.stderr)
            continue
        new = 0
        for it in items:
            if it["url"] in known:
                continue
            try:
                t = it.get("text") or detail(it["url"])
            except Exception as e:
                print(f"! {it['url']}: {e}", file=sys.stderr)
                continue
            c = classify(it["title"], t, it["source"], it["country"], it["deadline"])
            db.execute("INSERT INTO calls (url, title, source, country, deadline, closed, first_seen, funding, region, spatial, relevant, rev) "
                       "VALUES (:url, :title, :source, :country, :deadline, :closed, :first_seen, :funding, :region, :spatial, :relevant, :rev)",
                       dict(c, url=it["url"], title=it["title"], source=it["source"], country=it["country"], first_seen=today))
            known.add(it["url"])
            new += c["relevant"] and not c["closed"]
        db.commit()
        print(f"{src.__name__}: {len(items)} trovate, {new} nuove")


def open_calls(db):
    today = date.today().isoformat()
    # senza scadenza nota: mostrata per 60 giorni dalla prima volta che è stata vista
    stale = (date.today() - timedelta(days=60)).isoformat()
    rows = db.execute("SELECT * FROM calls WHERE relevant=1 AND COALESCE(closed, 0)=0 AND (deadline>=? OR (deadline='' AND first_seen>=?)) ORDER BY deadline='', deadline",
                      (today, stale))
    cols = [d[0] for d in rows.description]
    return [dict(zip(cols, r)) for r in rows]


def build_page(calls):
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    for c in calls:
        c["new"] = c["first_seen"] >= week_ago
    page = (HERE / "template.html").read_text().replace("/*DATA*/[]", json.dumps(calls, ensure_ascii=False)) \
        .replace("{{updated}}", datetime.now().strftime("%d.%m.%Y %H:%M"))
    out = HERE / "opencall.html"
    out.write_text(page)
    return out


def tg(token, method, **params):
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", urllib.parse.urlencode(params).encode(), timeout=30) as r:
        return json.load(r)


def telegram_config():
    """(token, chat_id) da config.ini o dalle variabili d'ambiente (secret di GitHub).
    Se manca il chat_id lo cerca tra i messaggi ricevuti dal bot."""
    cfg = configparser.ConfigParser()
    cfg.read(HERE / "config.ini")
    token = os.environ.get("TELEGRAM_TOKEN") or cfg.get("telegram", "token", fallback="").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID") or cfg.get("telegram", "chat_id", fallback="").strip()
    if not token:
        sys.exit("Token mancante: apri config.ini e incolla dopo 'token =' quello che ti ha dato @BotFather")
    if not chat:
        ids = {u[k]["chat"]["id"] for u in tg(token, "getUpdates")["result"] for k in u if k != "update_id" and "chat" in u[k]}
        sys.exit(f"Il tuo chat_id: {', '.join(map(str, ids))}  -> copialo in config.ini dopo 'chat_id =' e rilancia" if ids
                 else "Nessun messaggio ricevuto dal bot: apri il bot su Telegram, premi Avvia (o scrivi 'ciao') e rilancia")
    return token, chat


def tg_file(token, chat, path, caption):
    """sendDocument: multipart scritto a mano, la libreria standard non ha un helper."""
    b = "opencallboundary"
    name = f"opencall-{date.today().isoformat()}.html"
    body = (f'--{b}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{name}"\r\n'
            f'Content-Type: text/html\r\n\r\n').encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendDocument", body,
                                 {"Content-Type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=60).close()


def send_telegram(calls, token, chat, page):
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    new = [c for c in calls if c["first_seen"] > week_ago]  # > : quelle del lunedì scorso sono già state mandate
    url = os.environ.get("PAGE_URL")  # pagina online (GitHub Pages): link invece del file allegato
    parts = [f"<b>{len(new)} nuove open call questa settimana</b>"
             + (f'\n<a href="{url}">Tutte le {len(calls)} call aperte, con i filtri</a>' if url else "")]
    for fund in ("funded", "non funded", "a pagamento"):
        for reg in ("Austria", "Europa", "Mondo"):
            group = [c for c in new if c["funding"] == fund and c["region"] == reg]
            if group:
                parts.append(f"\n<b>{fund.upper()} · {reg} ({len(group)})</b>")
                parts += [f'• <a href="{html.escape(c["url"])}">{html.escape(c["title"], quote=False)}</a>\n'
                          f'   scadenza {c["deadline"] or "?"} · {c["source"]}' for c in group]
    msg = ""
    for p in parts:  # Telegram accetta al massimo 4096 caratteri per messaggio
        if len(msg) + len(p) > 4000:
            tg(token, "sendMessage", chat_id=chat, text=msg, parse_mode="HTML", disable_web_page_preview="true")
            msg = ""
        msg += p + "\n"
    tg(token, "sendMessage", chat_id=chat, text=msg, parse_mode="HTML", disable_web_page_preview="true")
    if not url:
        tg_file(token, chat, page, f"Tutte le {len(calls)} call aperte, con i filtri: aprila nel browser")
    print(f"telegram: inviate {len(new)} nuove")


def main():
    tg_cfg = telegram_config() if "--telegram" in sys.argv else None  # prima di scaricare, così un errore si vede subito
    db = sqlite3.connect(HERE / "opencall.db")
    print("Scarico le call (1-2 minuti)…", flush=True)
    db.execute("CREATE TABLE IF NOT EXISTS calls (url TEXT PRIMARY KEY, title, source, country, deadline, funding, region, first_seen)")
    cols = [r[1] for r in db.execute("PRAGMA table_info(calls)")]
    for col in ("spatial", "relevant", "rev", "closed"):  # colonne aggiunte dopo: il db su GitHub va aggiornato
        if col not in cols:
            db.execute(f"ALTER TABLE calls ADD COLUMN {col}")
    scrape(db)
    calls = open_calls(db)
    page = build_page(calls)
    print(f"{len(calls)} call aperte -> {page}")
    if tg_cfg:
        send_telegram(calls, *tg_cfg, page)
    else:
        if not os.environ.get("CI"):  # su GitHub non c'è un browser
            webbrowser.open(page.as_uri())


if __name__ == "__main__":
    main()
