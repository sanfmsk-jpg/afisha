/* Афиша мероприятий — клиентский сценарий */
(function () {
  'use strict';

  /* Переключение отметки «Пойду» без перезагрузки страницы */
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('.fav');
    if (!btn) { return; }
    ev.preventDefault();
    fetch('/api/favorites/' + btn.dataset.event, {
      method: 'POST',
      headers: { 'X-Requested-With': 'fetch' }
    }).then(function (r) {
      if (r.status === 302 || r.redirected) { location.href = '/login'; return null; }
      return r.json();
    }).then(function (data) {
      if (!data) { return; }
      btn.classList.toggle('is-on', data.added);
      btn.querySelector('.fav__count').textContent = data.count;
    }).catch(function () { location.href = '/login'; });
  });

  /* Шаблоны периода: выбор отключает ручной ввод дат */
  var form = document.getElementById('filters');
  if (form) {
    var presets = form.querySelectorAll('.chip input');
    var manual = form.querySelectorAll('input[type="date"]');
    presets.forEach(function (radio) {
      radio.addEventListener('change', function () {
        form.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-on'); });
        radio.closest('.chip').classList.add('is-on');
        if (radio.value !== 'all') {
          manual.forEach(function (i) { i.value = ''; });
        }
        form.submit();
      });
    });
    manual.forEach(function (input) {
      input.addEventListener('change', function () {
        var all = form.querySelector('.chip input[value="all"]');
        if (all) { all.checked = true; }
        form.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-on'); });
        if (all) { all.closest('.chip').classList.add('is-on'); }
      });
    });
    form.querySelectorAll('select, input[type="checkbox"]').forEach(function (el) {
      el.addEventListener('change', function () { form.submit(); });
    });
  }

  /* Вкладки личного кабинета */
  var tabs = document.getElementById('tabs');
  if (tabs) {
    tabs.addEventListener('click', function (ev) {
      var tab = ev.target.closest('.tab');
      if (!tab) { return; }
      tabs.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-on'); });
      tab.classList.add('is-on');
      document.querySelectorAll('.tabpane').forEach(function (p) { p.classList.remove('is-on'); });
      document.getElementById('pane-' + tab.dataset.tab).classList.add('is-on');
    });
  }
}());
