# baalbakhermel-data

بيانات موقع **دليل بعلبك والهرمل** (baalbakhermel.com).

## أسعار المحروقات
- `fuel.json` — أحدث جدول أسعار المحروقات الصادر عن وزارة الطاقة والمياه (بنزين 95، بنزين 98، المازوت، الغاز) مع الفرق عن الجدول السابق.
- يتحدّث تلقائياً عبر GitHub Actions (`.github/workflows/fuel.yml`) كل ساعتين بين 7 صباحاً و5 مساءً بتوقيت بيروت.
- `fuel-news.txt` — خبر جاهز للنسخ والنشر عن آخر جدول.
- المصدر: https://energyandwater.gov.lb/ar/prices?type=1
- المصدر الأساسي للأسعار: TotalEnergies لبنان، والوزارة احتياطياً.

## Green Goal Arena (greengoal.net)
- `greengoal/` — الأخبار الرياضية ومباريات اليوم ونتائجها لموقع الملعب، تنشرها مهمة Claude اليومية عبر `.github/workflows/greengoal.yml`. التفاصيل في `greengoal/README.md`.
- `site/greengoal-matches.html` — ودجت «مباريات اليوم» للصفحة الرئيسية.
