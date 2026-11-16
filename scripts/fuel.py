"""يجلب أسعار المحروقات من موقع وزارة الطاقة والمياه ويكتبها في fuel.json"""
import json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://energyandwater.gov.lb/ajax/pricesCtrl.php"
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
    html = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))["html"]
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


def main():
    liquid = fetch_rows(1)   # تاريخ | قرار | 95 | 98 | كاز | مازوت | ديزل أويل | تحميل
    gas = fetch_rows(5)      # تاريخ | قرار | قارورة غاز 10 كلغ | تحميل
    if len(liquid) < 2 or len(gas) < 2:
        sys.exit("لم أجد صفوفاً كافية في الجدول")
    c, p = liquid[0], liquid[1]
    g, gp = gas[0], gas[1]
    out = {
        "date_text": c[0],
        "date": iso_date(c[0]),
        "decision": c[1],
        "gas_date_text": g[0],
        "gas_date": iso_date(g[0]),
        "items": [
            item("بنزين 95 أوكتان", "ل.ل. / صفيحة 20 ليتر", num(c[2]), num(p[2]), iso_date(p[0])),
            item("بنزين 98 أوكتان", "ل.ل. / صفيحة 20 ليتر", num(c[3]), num(p[3]), iso_date(p[0])),
            item("المازوت (ديزل أويل)", "ل.ل. / صفيحة 20 ليتر", num(c[6]), num(p[6]), iso_date(p[0])),
            item("قارورة الغاز", "ل.ل. / قارورة 10 كلغ", num(g[2]), num(gp[2]), iso_date(gp[0])),
        ],
        "history": [{"date": iso_date(r[0]), "b95": num(r[2]), "b98": num(r[3]), "diesel": num(r[6])}
                    for r in liquid[:12]],
        "source": "وزارة الطاقة والمياه — energyandwater.gov.lb",
        "checked_at": datetime.now(timezone(timedelta(hours=2))).isoformat(timespec="minutes"),
    }
    if any(i["price"] <= 0 for i in out["items"]):
        sys.exit("سعر غير صالح، لن أكتب الملف: " + json.dumps(out["items"], ensure_ascii=False))

    # لا نعيد كتابة الملف إذا لم تتغيّر الأسعار (حتى لا ينشأ commit بلا سبب)
    try:
        old = json.load(open("fuel.json", encoding="utf-8"))
        if old.get("date") == out["date"] and old.get("items") == out["items"]:
            print("لا جديد:", out["date"])
            return
    except FileNotFoundError:
        pass
    json.dump(out, open("fuel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("تم التحديث:", out["date"])


if __name__ == "__main__":
    main()
