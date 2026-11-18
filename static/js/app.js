/* Афиша мероприятий — клиентский сценарий */
(function () {
  'use strict';

  /* Цели Яндекс Метрики (тип «JavaScript-событие»).
     Идентификаторы целей: registration, fav_add, filter_apply, cta_register.
     Все достижения дополнительно копятся в window.afishaGoals — так цели
     можно проверить и без настоящего счётчика (заглушка 00000000). */
  window.afishaGoals = window.afishaGoals || [];
  window.afishaGoal = function (name, params) {
    window.afishaGoals.push(name);
    var id = parseInt(window.AFISHA_YM_ID, 10);
    if (typeof window.ym === 'function' && id) {
      window.ym(id, 'reachGoal', name, params);
    }
  };

  /* Цель, поставленная сервером на один показ (успешная регистрация) */
  if (document.body.dataset.goalOnce) {
    window.afishaGoal(document.body.dataset.goalOnce);
  }

  /* Цели по клику: любой элемент с атрибутом data-goal */
  document.addEventListener('click', function (ev) {
    var el = ev.target.closest('[data-goal]');
    if (el) { window.afishaGoal(el.dataset.goal); }
  });

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
      btn.setAttribute('aria-pressed', data.added ? 'true' : 'false');
      btn.querySelector('.fav__count').textContent = data.count;
      if (data.added) { window.afishaGoal('fav_add'); }
    }).catch(function () { location.href = '/login'; });
  });

  /* Шаблоны периода: выбор отключает ручной ввод дат.
     Автоматическая отправка формы при смене значения убрана (WCAG 3.2.2):
     применить фильтры можно кнопкой «Показать» или клавишей Enter. */
  var form = document.getElementById('filters');
  if (form) {
    form.addEventListener('submit', function () { window.afishaGoal('filter_apply'); });
    var presets = form.querySelectorAll('.chip input');
    var manual = form.querySelectorAll('input[type="date"]');
    presets.forEach(function (radio) {
      radio.addEventListener('change', function () {
        form.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-on'); });
        radio.closest('.chip').classList.add('is-on');
        if (radio.value !== 'all') {
          manual.forEach(function (i) { i.value = ''; });
        }
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
  }

  /* Вкладки личного кабинета: шаблон ARIA «Tabs» (клик, стрелки, Home/End) */
  var tabs = document.getElementById('tabs');
  if (tabs) {
    var tabList = Array.prototype.slice.call(tabs.querySelectorAll('.tab'));
    var select = function (tab, focus) {
      tabList.forEach(function (t) {
        var on = t === tab;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
      });
      document.querySelectorAll('.tabpane').forEach(function (p) { p.classList.remove('is-on'); });
      document.getElementById('pane-' + tab.dataset.tab).classList.add('is-on');
      if (focus) { tab.focus(); }
    };
    tabs.addEventListener('click', function (ev) {
      var tab = ev.target.closest('.tab');
      if (tab) { select(tab, false); }
    });
    tabs.addEventListener('keydown', function (ev) {
      var i = tabList.indexOf(document.activeElement);
      if (i < 0) { return; }
      var next = null;
      if (ev.key === 'ArrowRight') { next = tabList[(i + 1) % tabList.length]; }
      if (ev.key === 'ArrowLeft') { next = tabList[(i - 1 + tabList.length) % tabList.length]; }
      if (ev.key === 'Home') { next = tabList[0]; }
      if (ev.key === 'End') { next = tabList[tabList.length - 1]; }
      if (next) { ev.preventDefault(); select(next, true); }
    });
  }
}());
