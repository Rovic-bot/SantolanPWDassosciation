const plugin = require('tailwindcss/plugin');

module.exports = {
  content: ['./templates/public/guidance/*.html'],
  // Keep the existing Bootstrap/public portal styles outside this section.
  important: '#main-content #home-guidance',
  corePlugins: {preflight: false},
  theme: {extend: {
    // Reuse the public portal tokens, including its dark and high-contrast overrides.
    colors: {portal: {
      canvas: 'var(--paper)',
      card: 'var(--surface)',
      inset: 'var(--stone)',
      ink: 'var(--ink)',
      muted: 'var(--muted)',
      border: 'var(--line)',
      control: 'var(--control-edge)',
      action: 'var(--brand-primary)',
      hover: 'var(--teal-hover)',
    }},
    boxShadow: {
      portal: 'var(--portal-shadow)',
      'portal-hover': '0 16px 40px -16px color-mix(in srgb, var(--ink) 20%, transparent)',
    },
  }},
  plugins: [plugin(({addVariant}) => {
    addVariant('portal-contrast', 'html[data-contrast="true"] &');
    addVariant('portal-motion', 'html[data-motion="reduce"] &');
    addVariant('touch', '@media (hover: none)');
  })],
};
