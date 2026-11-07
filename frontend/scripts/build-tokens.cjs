#!/usr/bin/env node
/**
 * design-tokens.json -> src/styles/tokens.css (три слоя: primitive -> semantic -> component).
 *
 * Базовый генератор навыка design-system (scripts/generate-tokens.cjs) раскрывает ссылки
 * в готовые значения: компонентный слой тогда не следует за переключением на .dark.
 * Этот скрипт читает тот же JSON, но сохраняет цепочку ссылок через var(--…), поэтому
 * тёмная тема переопределяет только семантические токены, а остальное подхватывается само.
 *
 * Запуск: node scripts/build-tokens.cjs
 */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const tokens = JSON.parse(fs.readFileSync(path.join(root, 'design-tokens.json'), 'utf8'));

/** Имя CSS-переменной по пути токена. Семантический слой — без префикса (имена shadcn). */
function varName(parts) {
  return '--' + parts.join('-');
}

/** `{semantic.primary}` -> `var(--primary)`, `{primitive.color.navy.700}` -> `var(--primitive-color-navy-700)`. */
function ref(value) {
  return String(value).replace(/\{([^}]+)\}/g, (_, p) => {
    const parts = p.split('.');
    return `var(${varName(parts[0] === 'semantic' ? parts.slice(1) : parts)})`;
  });
}

function flatten(node, prefix, out = []) {
  for (const [key, val] of Object.entries(node)) {
    if (val && typeof val === 'object' && val.$value === undefined) flatten(val, [...prefix, key], out);
    else out.push([varName([...prefix, key]), ref(val.$value)]);
  }
  return out;
}

const block = (selector, rows) =>
  `${selector} {\n${rows.map(([k, v]) => `  ${k}: ${v};`).join('\n')}\n}\n`;

const css = [
  '/* Автоматически из design-tokens.json: node scripts/build-tokens.cjs. Руками не править. */',
  '/* Слой 1. Primitive: сырые значения */',
  block(':root', flatten(tokens.primitive, ['primitive'])),
  '/* Слой 2. Semantic: назначение (имена shadcn/ui) */',
  block(':root', flatten(tokens.semantic, [])),
  '/* Слой 3. Component: значения для конкретных компонентов (ссылаются на semantic) */',
  block(':root', flatten(tokens.component, [])),
  '/* Тёмная тема: переопределены только семантические токены */',
  block('.dark', flatten(tokens.dark.semantic, [])),
].join('\n');

fs.writeFileSync(path.join(root, 'src/styles/tokens.css'), css);
console.log('src/styles/tokens.css обновлён');
