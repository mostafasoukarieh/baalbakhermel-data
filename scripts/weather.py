"""نشرة طقس يومية لبعلبك والهرمل تُنشر على بلوغر بوسم «طقس» (مرة واحدة في اليوم)."""
import html, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from blogger import BLOG_ID, access_token  # noqa: E402

LABELS = ["طقس"]
POST_HOUR = 7                     # ساعة النشر بتوقيت بيروت
WEATHER_PAGE_URL = os.environ.get("WEATHER_PAGE_URL", "")  # رابط صفحة الطقس المباشر (اختياري)
STATE_FILE = "weather-posted.json"
# الصورة الثابتة للنشرة (تظهر في روابط المشاركة على واتساب وفيسبوك)
IMAGE_URL = "https://raw.githubusercontent.com/mostafasoukarieh/baalbakhermel-data/main/assets/weather-og.jpg"
TZ = ZoneInfo("Asia/Beirut")

TOWNS = [
    ("بعلبك", 34.006, 36.218), ("الهرمل", 34.394, 36.385), ("دير الأحمر", 34.125, 36.130),
    ("شمسطار", 33.963, 36.060), ("بريتال", 33.945, 36.247), ("اللبوة", 34.196, 36.350),
    ("عرسال", 34.179, 36.420), ("الفاكهة", 34.233, 36.404), ("القاع", 34.343, 36.476),
]

WMO = {
    0: ("صحو", "☀️"), 1: ("صحو غالباً", "🌤️"), 2: ("غائم جزئياً", "⛅"), 3: ("غائم", "☁️"),
    45: ("ضباب", "🌫️"), 48: ("ضباب مع صقيع", "🌫️"),
    51: ("رذاذ خفيف", "🌦️"), 53: ("رذاذ", "🌦️"), 55: ("رذاذ كثيف", "🌧️"),
    56: ("رذاذ متجمّد", "🌧️"), 57: ("رذاذ متجمّد كثيف", "🌧️"),
    61: ("أمطار خفيفة", "🌦️"), 63: ("أمطار", "🌧️"), 65: ("أمطار غزيرة", "🌧️"),
    66: ("أمطار متجمّدة", "🌧️"), 67: ("أمطار متجمّدة غزيرة", "🌧️"),
    71: ("ثلوج خفيفة", "🌨️"), 73: ("ثلوج", "❄️"), 75: ("ثلوج كثيفة", "❄️"), 77: ("حبيبات ثلج", "🌨️"),
    80: ("زخات مطر خفيفة", "🌦️"), 81: ("زخات مطر", "🌧️"), 82: ("زخات مطر غزيرة", "⛈️"),
    85: ("زخات ثلج", "🌨️"), 86: ("زخات ثلج كثيفة", "❄️"),
    95: ("عواصف رعدية", "⛈️"), 96: ("عواصف رعدية مع برَد", "⛈️"), 99: ("عواصف رعدية مع برَد كثيف", "⛈️"),
}
AR_MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب",
             "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
AR_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def w(code):
    return WMO.get(code, ("—", "🌡️"))


def ar_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]}"


def day_name(iso, i):
    return "اليوم" if i == 0 else "غداً" if i == 1 else AR_DAYS[datetime.strptime(iso, "%Y-%m-%d").weekday()]


DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
         "precipitation_probability_max,snowfall_sum,wind_gusts_10m_max,sunrise,sunset")
CURRENT = "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day"
UA = {"User-Agent": "baalbakhermel.com weather (github.com/mostafasoukarieh/baalbakhermel-data)"}


def get_json(url, timeout=40):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read())


def fetch_open_meteo(days=3, current=False):
    q = {"latitude": ",".join(str(t[1]) for t in TOWNS), "longitude": ",".join(str(t[2]) for t in TOWNS),
         "daily": DAILY, "timezone": "Asia/Beirut", "forecast_days": days}
    if current:
        q["current"] = CURRENT
    data = get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    return data if isinstance(data, list) else [data]


# ---------- مصدر احتياطي: المعهد النرويجي للأرصاد (MET Norway) ----------
MET_CODE = [("thunder", 95), ("heavysnow", 75), ("lightsnow", 71), ("snowshowers", 85), ("snow", 73),
            ("sleet", 66), ("heavyrainshowers", 82), ("lightrainshowers", 80), ("rainshowers", 81),
            ("heavyrain", 65), ("lightrain", 61), ("rain", 63), ("fog", 45), ("cloudy", 3),
            ("partlycloudy", 2), ("fair", 1), ("clearsky", 0)]


def met_code(sym):
    sym = (sym or "").split("_")[0]
    for k, c in MET_CODE:
        if sym == k or (k in ("thunder",) and k in sym):
            return c
    for k, c in MET_CODE:
        if sym.startswith(k):
            return c
    return 3


SUN = {}


def sun_times(day):
    """شروق الشمس وغروبها في بعلبك (الفرق بين البلدات دقيقة أو اثنتان)."""
    if day not in SUN:
        try:
            sp = get_json(f"https://api.met.no/weatherapi/sunrise/3.0/sun?lat=34.006&lon=36.218&date={day}&offset=+02:00")["properties"]
            SUN[day] = (sp["sunrise"]["time"][:16], sp["sunset"]["time"][:16])
        except Exception:  # noqa: BLE001
            SUN[day] = (day + "T06:15", day + "T16:30")
    return SUN[day]


def fetch_met(days=3, current=False):
    out = []
    for _, lat, lon in TOWNS:
        ts = get_json(f"https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={lat}&lon={lon}")["properties"]["timeseries"]
        by_day = {}
        cur = None
        for e in ts:
            t = datetime.fromisoformat(e["time"].replace("Z", "+00:00")).astimezone(TZ)
            det = e["data"]["instant"]["details"]
            nxt = e["data"].get("next_1_hours") or e["data"].get("next_6_hours") or {}
            nd = nxt.get("details", {})
            hours = 1 if "next_1_hours" in e["data"] else 6
            dd = by_day.setdefault(t.strftime("%Y-%m-%d"), {"t": [], "p": 0.0, "pp": [], "g": [], "codes": [], "snow": 0.0})
            dd["t"].append(det.get("air_temperature"))
            if "wind_speed_of_gust" in det:
                dd["g"].append(det["wind_speed_of_gust"] * 3.6)
            if "probability_of_precipitation" in nd:
                dd["pp"].append(nd["probability_of_precipitation"])
            sym = nxt.get("summary", {}).get("symbol_code")
            if sym and (hours == 1 or t.hour % 6 == 0):
                amt = nd.get("precipitation_amount", 0) or 0
                dd["p"] += amt
                c = met_code(sym)
                if c in (71, 73, 75, 85):
                    dd["snow"] += amt
                if 6 <= t.hour <= 18:
                    dd["codes"].append(c)
            if cur is None:
                cur = {"temperature_2m": det.get("air_temperature"), "relative_humidity_2m": det.get("relative_humidity"),
                       "apparent_temperature": det.get("air_temperature"), "weather_code": met_code(sym),
                       "wind_speed_10m": round((det.get("wind_speed") or 0) * 3.6, 1),
                       "is_day": 1 if 6 <= t.hour < 18 else 0}
        keys = sorted(by_day)[:days]
        daily = {k: [] for k in DAILY.split(",")}
        daily["time"] = keys
        for k in keys:
            dd = by_day[k]
            temps = [x for x in dd["t"] if x is not None]
            codes = dd["codes"] or [3]
            # الحالة الغالبة في النهار، مع تقديم المطر/الثلج/العواصف إن ظهرت ساعتين أو أكثر
            wet = [c for c in codes if c >= 45]
            code = max(set(wet), key=wet.count) if len(wet) >= 2 else max(set(codes), key=codes.count)
            daily["weather_code"].append(code)
            daily["temperature_2m_max"].append(max(temps))
            daily["temperature_2m_min"].append(min(temps))
            daily["precipitation_sum"].append(round(dd["p"], 1))
            daily["precipitation_probability_max"].append(round(max(dd["pp"])) if dd["pp"] else (60 if dd["p"] >= 1 else 0))
            daily["snowfall_sum"].append(round(dd["snow"], 1))
            daily["wind_gusts_10m_max"].append(round(max(dd["g"]), 1) if dd["g"] else 0)
            sr, ss = sun_times(k)
            daily["sunrise"].append(sr)
            daily["sunset"].append(ss)
        loc = {"latitude": lat, "longitude": lon, "daily": daily, "source": "MET Norway"}
        if current:
            loc["current"] = cur
        out.append(loc)
    return out


def fetch(days=3, current=False):
    """Open-Meteo مع 3 محاولات، ثم المصدر الاحتياطي MET Norway."""
    global SOURCE
    waits = () if os.environ.get("WEATHER_SOURCE") == "met" else (0, 20, 60)
    for wait in waits:
        if wait:
            time.sleep(wait)
        try:
            data = fetch_open_meteo(days, current)
            SOURCE = "Open-Meteo"
            return data
        except Exception as e:  # noqa: BLE001
            print("Open-Meteo فشل:", e)
    print("الانتقال إلى المصدر الاحتياطي MET Norway")
    SOURCE = "MET Norway"
    return fetch_met(days, current)


SOURCE = "Open-Meteo"


def snapshot():
    """يحفظ weather.json (بصيغة Open-Meteo) لتستعمله صفحة الطقس إذا تعذّر الاتصال المباشر."""
    data = fetch(days=7, current=True)
    for loc in data:
        loc["source"] = SOURCE
    json.dump({"updated": datetime.now(TZ).isoformat(timespec="minutes"), "source": SOURCE, "towns": [t[0] for t in TOWNS],
               "data": data}, open("weather.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("تم حفظ weather.json من", SOURCE)


def alerts(locs):
    groups = {}

    def add(key, label, town, day):
        g = groups.setdefault(key, {"label": label, "towns": [], "days": []})
        if town not in g["towns"]:
            g["towns"].append(town)
        if day not in g["days"]:
            g["days"].append(day)

    for (town, *_), loc in zip(TOWNS, locs):
        d = loc["daily"]
        for i in range(2):
            day, c = day_name(d["time"][i], i), d["weather_code"][i]
            if (d["snowfall_sum"][i] or 0) > 0 or c in (71, 73, 75, 77, 85, 86):
                add("snow", "❄️ تساقط ثلوج", town, day)
            if d["temperature_2m_min"][i] <= 0:
                add("frost", "🥶 صقيع وجليد — الحذر على الطرقات وحماية المزروعات", town, day)
            if (d["precipitation_sum"][i] or 0) >= 15:
                add("rain", "🌧️ أمطار غزيرة — احتمال تجمّع مياه وسيول", town, day)
            if (d["wind_gusts_10m_max"][i] or 0) >= 60:
                add("wind", "💨 رياح قوية (هبّات تفوق 60 كم/س)", town, day)
            if c >= 95:
                add("storm", "⛈️ عواصف رعدية", town, day)
            if d["temperature_2m_max"][i] >= 35:
                add("heat", "🔥 موجة حرّ — تجنّبوا الشمس وقت الظهيرة", town, day)
            if c in (45, 48):
                add("fog", "🌫️ ضباب — انتبهوا لانخفاض الرؤية أثناء القيادة", town, day)
    return list(groups.values())


def build(locs):
    b, h = locs[0]["daily"], locs[1]["daily"]
    today = b["time"][0]
    bt, bi = w(b["weather_code"][0])
    r = round
    title = (f"{bi} طقس بعلبك والهرمل اليوم {ar_date(today)}: {bt}، "
             f"والحرارة بين {r(b['temperature_2m_min'][0])} و{r(b['temperature_2m_max'][0])} درجة")

    p = [f"<p style='text-align:center'><img src='{IMAGE_URL}' alt='طقس بعلبك والهرمل' width='1200' height='630' "
         "style='max-width:100%;height:auto;border-radius:12px'></p>"]
    p.append(f"<p>الطقس اليوم في <b>بعلبك</b> {bt}، والحرارة بين {r(b['temperature_2m_min'][0])} "
             f"و{r(b['temperature_2m_max'][0])} درجة مئوية. وفي <b>الهرمل</b> {w(h['weather_code'][0])[0]}، "
             f"والحرارة بين {r(h['temperature_2m_min'][0])} و{r(h['temperature_2m_max'][0])} درجة.</p>")
    if (b["precipitation_probability_max"][0] or 0) >= 40:
        p.append(f"<p>احتمال هطول الأمطار في بعلبك اليوم {b['precipitation_probability_max'][0]}%.</p>")
    p.append(f"<p>شروق الشمس {b['sunrise'][0][11:16]} وغروبها {b['sunset'][0][11:16]}.</p>")

    if WEATHER_PAGE_URL:
        p.append(f"<p>👈 <a href='{html.escape(WEATHER_PAGE_URL)}'><b>تابعوا الطقس لحظة بلحظة</b></a></p>")
    al = alerts(locs)
    if al:
        p.append("<h3>⚠️ تنبيهات</h3><ul>" + "".join(
            f"<li><b>{html.escape(a['label'])}</b> — {'، '.join(a['days'])}: {'، '.join(a['towns'])}</li>"
            for a in al) + "</ul>")

    rows = []
    for (town, *_), loc in zip(TOWNS, locs):
        d = loc["daily"]
        t, ic = w(d["weather_code"][0])
        rows.append(f"<tr><td><b>{town}</b></td><td>{ic} {t}</td>"
                    f"<td dir='ltr'>{r(d['temperature_2m_min'][0])}° / {r(d['temperature_2m_max'][0])}°</td>"
                    f"<td dir='ltr'>{d['precipitation_probability_max'][0] or 0}%</td></tr>")
    p.append("<h3>🌡️ الطقس اليوم في البلدات</h3>"
             "<table border='1' cellpadding='7' style='border-collapse:collapse;width:100%;text-align:center'>"
             "<tr style='background:#e8f3f8'><th>البلدة</th><th>الحالة</th><th>الصغرى / العظمى</th><th>احتمال المطر</th></tr>"
             + "".join(rows) + "</table>")

    tt, ti = w(b["weather_code"][1])
    diff = b["temperature_2m_max"][1] - b["temperature_2m_max"][0]
    trend = "، مع انخفاض ملحوظ في الحرارة" if diff <= -3 else "، مع ارتفاع ملحوظ في الحرارة" if diff >= 3 else ""
    p.append(f"<h3>📅 غداً</h3><p>{ti} في بعلبك {tt}، والحرارة بين {r(b['temperature_2m_min'][1])} "
             f"و{r(b['temperature_2m_max'][1])} درجة{trend}.</p>")

    if WEATHER_PAGE_URL:
        p.append(f"<p style='text-align:center;margin:22px 0'><a href='{html.escape(WEATHER_PAGE_URL)}' "
                 "style='display:inline-block;background:#1e6091;color:#fff;text-decoration:none;"
                 "padding:12px 26px;border-radius:30px;font-weight:bold;font-size:1.05em'>"
                 "🌦️ الطقس المباشر وتوقعات الأسبوع ←</a></p>")
    p.append(f"<p><small>مصدر البيانات: {SOURCE}</small></p>")
    return today, title, "<div dir='rtl'>" + "".join(p) + "</div>"


def main():
    mode = os.environ.get("BLOGGER_MODE", "publish")
    if mode == "snapshot":
        snapshot()
        return
    force = os.environ.get("FORCE") == "1"
    now = datetime.now(TZ)
    if not force and now.hour < POST_HOUR:
        print("لم تحن الساعة بعد:", now.strftime("%H:%M"))
        return
    state = json.load(open(STATE_FILE, encoding="utf-8")) if os.path.exists(STATE_FILE) else {}
    if mode == "publish" and state.get("date") == now.strftime("%Y-%m-%d"):
        print("نُشرت نشرة اليوم سابقاً، تحديث النسخة الاحتياطية فقط")
        snapshot()
        return

    today, title, content = build(fetch())
    if os.environ.get("DRY_RUN") == "1":
        print(title)
        print(content)
        return

    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    if mode != "publish":
        url += "?isDraft=true"
    req = urllib.request.Request(url, method="POST",
                                 data=json.dumps({"kind": "blogger#post", "title": title,
                                                  "content": content, "labels": LABELS}).encode(),
                                 headers={"Authorization": "Bearer " + access_token(),
                                          "Content-Type": "application/json; charset=utf-8"})
    try:
        post = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"فشل النشر على بلوغر: {e.code} {e.read().decode()[:500]}")
    print("تم:", post.get("status"), post.get("url") or post.get("id"))
    if mode == "publish":   # المسودات التجريبية لا تمنع نشر نشرة اليوم
        json.dump({"date": today, "post_id": post.get("id"), "url": post.get("url")},
                  open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        try:
            snapshot()
        except Exception as e:  # noqa: BLE001
            print("تعذّر حفظ النسخة الاحتياطية:", e)


if __name__ == "__main__":
    main()
