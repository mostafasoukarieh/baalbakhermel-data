/**
 * مُشغِّل مواعيد «دليل بعلبك والهرمل»
 * يشغّل سكربتات GitHub في مواعيدها لأن الجدولة في GitHub لا تعمل على هذا المستودع.
 *
 * الإعداد مرة واحدة:
 * 1) Project Settings ← Time zone = (GMT+02:00) Beirut
 * 2) Project Settings ← Script Properties ← أضف:
 *      GITHUB_TOKEN = رمز GitHub (Fine-grained، للمستودع baalbakhermel-data فقط، صلاحية Actions: Read and write)
 * 3) اختر الدالة installTriggers من القائمة واضغط Run، ثم وافق على الأذونات.
 */

var REPO = 'mostafasoukarieh/baalbakhermel-data';

function dispatch_(workflow, inputs) {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN غير موجود في Script Properties');
  var res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/actions/workflows/' + workflow + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main', inputs: inputs || {} }),
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 204) throw new Error(workflow + ': ' + res.getResponseCode() + ' ' + res.getContentText());
  console.log('تم تشغيل ' + workflow);
}

/** يعمل كل ساعة: أسعار المحروقات + نسخة الطقس الاحتياطية + إعادة محاولة نشرة الطقس */
function runFuel() {
  var h = Number(Utilities.formatDate(new Date(), 'Asia/Beirut', 'H'));
  var jobs = [];
  if (h >= 7 && h <= 18) jobs.push(['fuel.yml', { update_post: 'false' }]);
  // إذا فشلت نشرة الصباح، تُعاد المحاولة كل ساعة حتى الظهر (السكربت لا ينشر نشرتين في اليوم)
  if (h >= 8 && h <= 13) jobs.push(['weather.yml', { mode: 'publish' }]);
  // نسخة احتياطية لصفحة الطقس المباشر
  else if (h >= 6 && h <= 23) jobs.push(['weather.yml', { mode: 'snapshot' }]);
  jobs.forEach(function (j) {
    try { dispatch_(j[0], j[1]); } catch (e) { console.error(e); }
  });
}

/** نشرة الطقس اليومية (السكربت نفسه يمنع نشر نشرتين في اليوم نفسه) */
function runWeather() {
  dispatch_('weather.yml', { mode: 'publish' });
}

/** شغّلها مرة واحدة فقط لإنشاء المواعيد */
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('runFuel').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('runWeather').timeBased().atHour(7).everyDays(1).inTimezone('Asia/Beirut').create();
  console.log('تم إنشاء المواعيد');
}
