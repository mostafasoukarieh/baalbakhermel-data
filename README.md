# baalbakhermel-data

بيانات موقع **دليل بعلبك والهرمل** (baalbakhermel.com).

## أسعار المحروقات
- `fuel.json` — أحدث جدول أسعار المحروقات الصادر عن وزارة الطاقة والمياه (بنزين 95، بنزين 98، المازوت، الغاز) مع الفرق عن الجدول السابق.
- يتحدّث تلقائياً عبر GitHub Actions (`.github/workflows/fuel.yml`) كل ساعتين بين 7 صباحاً و5 مساءً بتوقيت بيروت.
- `fuel-news.txt` — خبر جاهز للنسخ والنشر عن آخر جدول.
- المصدر: https://energyandwater.gov.lb/ar/prices?type=1
