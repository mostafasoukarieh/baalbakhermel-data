"""يجلب أسعار المحروقات من موقع وزارة الطاقة والمياه ويكتبها في fuel.json"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://energyandwater.gov.lb/ajax/pricesCtrl.php"
USD_RATE = 89700  # سعر الدولار بالليرة المعتمد
MONTHS = {"كانون ثاني": 1, "كانون الثاني": 1, "شباط": 2, "آذار": 3, "اذار": 3, "نيسان": 4,
          "أيار": 5, "ايار": 5, "حزيران": 6, "تموز": 7, "آب": 8, "اب": 8, "أيلول": 9, "ايلول": 9,
          "تشرين أول": 10, "تشرين الأول": 10, "تشرين اول": 10, "تشرين ثاني": 11, "تشرين الثاني": 11,
          "كانون أول": 12, "كانون الأول": 12, "كانون اول": 12}


def fetch_rows(type_id):
    data = urllib.parse.urlencode({"action": "RenderPrices", "priceTypeId": type_id,
                                   "page": 0, "fromDate": "", "toDate": ""}).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (baalbakhermel.com fuel prices bot)",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://energyandwater.gov.lb/ar/prices?type={type_id}"})
    html = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig"))["html"]
    body = html.split("<tbody>", 1)[1]
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = [re.sub(r"<[^>]+>", "", td).strip() for td in re.findall(r"<td>(.*?)</td>", tr, re.S)]
        rows.append(cells)
    return rows


def num(s):
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else 0


def iso_date(ar):
    # مثال: "الثلاثاء, 10 تشرين ثاني 2026"
    m = re.search(r"(\d{1,2})\s+(.+?)\s+(\d{4})", ar)
    if not m:
        return None
    month = MONTHS.get(m.group(2).strip())
    return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}" if month else None


def item(name, unit, cur, prev, prev_date):
    return {"name": name, "unit": unit, "price": cur,
            "change": cur - prev if prev else 0, "prev_date": prev_date}


AR_MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب",
             "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
AR_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def ar_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]} {d.year}"


def change_text(c):
    if c > 0:
        return f"(+{c:,})"
    if c < 0:
        return f"(-{-c:,})"
    return "(دون تغيير)"


def news_text(out):
    it = out["items"]
    trend = sum(i["change"] for i in it[:3])
    title = ("ارتفاع في أسعار المحروقات" if trend > 0 else
             "انخفاض في أسعار المحروقات" if trend < 0 else "استقرار أسعار المحروقات")
    lines = [f"⛽ {title} — جدول {ar_date(out['date'])}", "",
             "صدر عن وزارة الطاقة والمياه جدول جديد لأسعار المحروقات، وجاءت الأسعار على الشكل التالي:", ""]
    for i in it[:3]:
        lines.append(f"• {i['name']}: {i['price']:,} ل.ل. {change_text(i['change'])} — ${i['price'] / USD_RATE:.2f}")
    g = it[3]
    gas_ch = change_text(g["change"]) if out["gas_date"] == out["date"] else "(دون تغيير)"
    lines.append(f"• {g['name']}: {g['price']:,} ل.ل. {gas_ch} — ${g['price'] / USD_RATE:.2f}")
    lines += ["", "الأسعار بالليرة اللبنانية لصفيحة 20 ليتر، وقارورة الغاز 10 كلغ.",
              f"السعر بالدولار على أساس {USD_RATE:,} ليرة للدولار.",
              *([f"الفرق مقارنة بجدول {ar_date(it[0]['prev_date'])}."] if it[0].get("prev_date") else []),
              "المصدر: وزارة الطاقة والمياه", "", "#دليل_بعلبك_والهرمل #أسعار_المحروقات"]
    return "\n".join(lines) + "\n"


TOTAL_URL = "https://pricing.totalenergies.com.lb/fuelprice/"
TOTAL_CODES = {"excellium-unleaded-95": "b95", "excellium-unleaded-98": "b98", "diesel": "diesel", "gasoil": "gas"}
NAMES = [("b95", "بنزين 95 أوكتان", "ل.ل. / صفيحة 20 ليتر"), ("b98", "بنزين 98 أوكتان", "ل.ل. / صفيحة 20 ليتر"),
         ("diesel", "المازوت (ديزل أويل)", "ل.ل. / صفيحة 20 ليتر"), ("gas", "قارورة الغاز", "ل.ل. / قارورة 10 كلغ")]


def from_total():
    """المصدر الأساسي: صفحة أسعار توتال لبنان (تتحدّث أسرع من موقع الوزارة)."""
    req = urllib.request.Request(TOTAL_URL, headers={"User-Agent": "Mozilla/5.0 (baalbakhermel.com fuel prices bot)"})
    h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    m = re.search(r'class="divToday"[^>]*>\s*(\d{1,2})/(\d{1,2})/(\d{4})', h)
    if not m:
        raise ValueError("لم أجد التاريخ في صفحة توتال")
    date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    vals = dict(re.findall(r'id="v(\d+)">\s*([\d,]+)\s*<', h))
    ids = dict(re.findall(r'id="id(\d+)">\s*([\w-]+)\s*<', h))
    prices = {TOTAL_CODES[code]: num(vals[n]) for n, code in ids.items() if code in TOTAL_CODES and n in vals}
    return date, prices, "TotalEnergies لبنان"


def from_ministry():
    """المصدر الاحتياطي: جدول وزارة الطاقة والمياه."""
    c = fetch_rows(1)[0]   # تاريخ | قرار | 95 | 98 | كاز | مازوت | ديزل أويل | تحميل
    g = fetch_rows(5)[0]   # تاريخ | قرار | قارورة غاز 10 كلغ | تحميل
    return iso_date(c[0]), {"b95": num(c[2]), "b98": num(c[3]), "diesel": num(c[6]), "gas": num(g[2])}, \
        "وزارة الطاقة والمياه"


def main():
    try:
        old = json.load(open("fuel.json", encoding="utf-8"))
    except FileNotFoundError:
        old = {}
    oldp = {k: it["price"] for (k, *_), it in zip(NAMES, old.get("items", []))}

    try:
        date, prices, source = from_total()
    except Exception as e:  # noqa: BLE001
        print("تعذّر موقع توتال، أستعمل موقع الوزارة:", e)
        date, prices, source = from_ministry()
        if old.get("date") and date and date <= old["date"]:
            print("جدول الوزارة ليس أحدث مما عندنا:", date)
            return

    if set(prices) != {"b95", "b98", "diesel", "gas"} or not all(500_000 < v < 20_000_000 for v in prices.values()):
        sys.exit("أسعار غير صالحة، لن أكتب الملف: " + json.dumps(prices, ensure_ascii=False))

    unchanged = prices == oldp and old.get("usd_rate") == USD_RATE and os.path.exists("fuel-news.txt")
    if unchanged:
        print("لا جديد، آخر جدول:", old.get("date"), "— المصدر:", source)
        return
    if prices == oldp:          # تغيّر سعر الدولار فقط: لا نغيّر تاريخ الجدول
        date = old.get("date", date)

    new_table = prices != oldp
    items = []
    for (key, name, unit), o in zip(NAMES, old.get("items") or [{}] * 4):
        if new_table:
            prev = oldp.get(key)
            change, prev_date = (prices[key] - prev if prev else 0), old.get("date")
        else:                   # تغيّر سعر الدولار فقط: نُبقي الفروقات كما هي
            change, prev_date = o.get("change", 0), o.get("prev_date")
        items.append({"name": name, "unit": unit, "price": prices[key], "change": change, "prev_date": prev_date})
    gas_same = oldp.get("gas") == prices["gas"]
    hist = [{"date": date, "b95": prices["b95"], "b98": prices["b98"], "diesel": prices["diesel"]}]
    hist += [r for r in old.get("history", []) if r.get("date") != date]
    out = {
        "date_text": ar_date(date),
        "date": date,
        "decision": "",
        "gas_date": old.get("gas_date", date) if gas_same else date,
        "items": items,
        "history": hist[:12],
        "usd_rate": USD_RATE,
        "source": source,
        "checked_at": datetime.now(timezone(timedelta(hours=2))).isoformat(timespec="minutes"),
    }
    json.dump(out, open("fuel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open("fuel-news.txt", "w", encoding="utf-8").write(news_text(out))
    print("تم التحديث:", date, "— المصدر:", source)


if __name__ == "__main__":
    main()
