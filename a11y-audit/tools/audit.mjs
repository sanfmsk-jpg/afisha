// Автоматизированная (axe-core) и ручная (клавиатура, масштаб, заголовки) проверка.
// Запуск: node audit.mjs <before|after> [baseUrl]
import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const stage = process.argv[2] || 'before';
const base = process.argv[3] || 'http://127.0.0.1:5051';
const out = path.resolve('..', 'results', stage);
const shots = path.resolve('..', 'screens', stage);
fs.mkdirSync(out, { recursive: true });
fs.mkdirSync(shots, { recursive: true });

const PAGES = [
  ['catalog', '/'],
  ['event', '/event/1'],
  ['login', '/login'],
  ['register', '/register'],
  ['profile', '/profile', 'user'],
  ['event-user', '/event/1', 'user'],
  ['admin', '/admin', 'admin'],
  ['moderation', '/admin/moderation', 'admin'],
  ['event-form', '/admin/events/1/edit', 'admin'],
];
const CREDS = { user: ['maria@mail.ru', 'user123'], admin: ['admin@afisha.ru', 'admin123'] };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
});

const summary = {};
const contexts = {};
async function ctxFor(role) {
  if (!role) return browser;
  if (contexts[role]) return contexts[role];
  const ctx = await browser.createBrowserContext();
  const p = await ctx.newPage();
  await p.goto(base + '/login', { waitUntil: 'networkidle0' });
  await p.type('input[name=email]', CREDS[role][0]);
  await p.type('input[name=password]', CREDS[role][1]);
  await Promise.all([p.waitForNavigation(), p.click('button[type=submit]')]);
  await p.close();
  return (contexts[role] = ctx);
}
for (const [name, url, role] of PAGES) {
  const page = await (await ctxFor(role)).newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.goto(base + url, { waitUntil: 'networkidle0' });

  // --- axe-core ---
  await page.evaluate(axeSource);
  const axeRes = await page.evaluate(async (tags) => {
    const r = await axe.run(document, { runOnly: { type: 'tag', values: tags } });
    return {
      violations: r.violations.map(v => ({
        id: v.id, impact: v.impact, help: v.help, tags: v.tags.filter(t => t.startsWith('wcag')),
        nodes: v.nodes.map(n => ({ target: n.target.join(' '), html: n.html.slice(0, 140), summary: n.failureSummary })),
      })),
      passes: r.passes.length, incomplete: r.incomplete.map(i => ({ id: i.id, help: i.help, count: i.nodes.length })),
    };
  }, TAGS);

  // --- ручные проверки в браузере ---
  const manual = await page.evaluate(() => {
    const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => h.tagName + ': ' + h.textContent.trim().slice(0, 40));
    const imgs = [...document.querySelectorAll('img')].map(i => i.getAttribute('alt'));
    return {
      lang: document.documentElement.lang,
      title: document.title,
      headings: heads,
      h1count: document.querySelectorAll('h1').length,
      images: imgs.length,
      imagesNoAlt: imgs.filter(a => a === null).length,
      landmarks: ['header', 'nav', 'main', 'footer'].map(t => t + '=' + document.querySelectorAll(t).length),
      skipLink: !!document.querySelector('a[href="#main"], a[href="#content"], .skip'),
    };
  });

  // --- клавиатура: проходим Tab и фиксируем, виден ли фокус ---
  const tabStops = [];
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const same = window.__last === e;
      const seen = !same && e.dataset.a11ySeen === '1';
      window.__last = e;
      e.dataset.a11ySeen = '1';
      const cs = getComputedStyle(e);
      // у скрытого радио-чипа фокус показывает родитель
      const holder = e.closest('.chip') || e;
      const hs = getComputedStyle(holder);
      const hasOutline = (s) => s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
      const r = e.getBoundingClientRect();
      const label = (e.getAttribute('aria-label') || e.textContent || e.name || '').trim().replace(/\s+/g, ' ').slice(0, 30);
      return {
        seen, same,
        tag: e.tagName.toLowerCase() + (e.type ? '[' + e.type + ']' : ''), label,
        outlineSelf: hasOutline(cs) && parseFloat(cs.opacity) > 0, outlineHolder: hasOutline(hs),
        boxShadow: cs.boxShadow !== 'none', opacity: cs.opacity, w: Math.round(r.width), h: Math.round(r.height),
        y: Math.round(r.top + window.scrollY),
      };
    });
    if (!info) break;
    if (info.seen) break;
    if (info.same) continue;
    tabStops.push(info);
  }

  // --- масштаб 200 % (эмуляция ширины 640px при дефолтных 1280) ---
  await page.setViewport({ width: 640, height: 450, deviceScaleFactor: 2 });
  await page.reload({ waitUntil: 'networkidle0' });
  const zoom = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
    hOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  }));
  await page.screenshot({ path: path.join(shots, `${name}-zoom200.png`) });

  // --- скриншот страницы и с фокусом ---
  await page.setViewport({ width: 1280, height: 900 });
  await page.reload({ waitUntil: 'networkidle0' });
  await page.screenshot({ path: path.join(shots, `${name}.png`) });
  for (let i = 0; i < 6; i++) await page.keyboard.press('Tab');
  await page.screenshot({ path: path.join(shots, `${name}-tab6.png`) });

  summary[name] = { url, axe: axeRes, manual, tabStops, zoom };
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(out, 'audit.json'), JSON.stringify(summary, null, 2));

for (const [n, s] of Object.entries(summary)) {
  console.log(`\n=== ${n} === axe violations: ${s.axe.violations.length}, passes: ${s.axe.passes}`);
  for (const v of s.axe.violations) console.log(`  [${v.impact}] ${v.id} (${v.tags.join(',')}) x${v.nodes.length}: ${v.help}`);
  console.log('  lang=%s h1=%d skip=%s landmarks=%s imgs=%d/%d noalt', s.manual.lang, s.manual.h1count, s.manual.skipLink, s.manual.landmarks.join(','), s.manual.images, s.manual.imagesNoAlt);
  console.log('  headings:', s.manual.headings.slice(0, 6).join(' | '));
  const noFocus = s.tabStops.filter(t => !t.outlineSelf && !t.outlineHolder && !t.boxShadow);
  console.log(`  tab stops: ${s.tabStops.length}, без видимого фокуса: ${noFocus.length}`, noFocus.slice(0, 5).map(t => t.tag + ':' + t.label).join(' ; '));
  console.log('  zoom200 horizontal overflow:', s.zoom.hOverflow, s.zoom.scrollW + '/' + s.zoom.clientW);
}
