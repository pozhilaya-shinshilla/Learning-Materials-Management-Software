// Tailwind v4 выдаёт @layer; браузеры из ТЗ (Chrome 90–98, Safari 14–15.3, Firefox 88–96)
// их не знают и отбросили бы весь стиль. Плагин cascade-layers разворачивает слои в обычные
// правила с той же силой каскада.
export default {
  plugins: {
    '@tailwindcss/postcss': {},
    '@csstools/postcss-cascade-layers': {},
  },
}
