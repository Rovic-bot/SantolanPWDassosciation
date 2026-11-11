# Guidance colors aligned with the public portal

November 10, 2026. Owner-authorized presentation follow-up to the home guidance grid.

The five guidance cards now use the public portal's existing warm neutral palette through Tailwind aliases for the shared CSS tokens. The section background, cards, icon containers, text, borders, actions and hover shadows follow the active display preferences.

| Mode | Section | Cards | Text |
| --- | --- | --- | --- |
| Light | Warm beige `#e8e5df` | Cream `#f4f2ec` | Charcoal `#1c1a18`, secondary `#6b665f` |
| Dark | Warm black `#191817` | Charcoal `#242220` | Cream `#f4f2ec`, secondary `#c5c0b8` |
| High contrast, with either theme | White | White, dark outlines | `#111`, secondary `#333` |

High contrast removes decorative shadows and retains visible hover/focus borders. A scoped Tailwind token override on the section follows the current high-contrast palette despite legacy inherited variables in `public-make.css`. Shared portal styles were not changed.

The existing card grid, hover and keyboard reveal, touch support, reduced-motion utilities, published content and action destinations are retained. No business logic, database records or migrations changed.

## Verification

- `npm run build:guidance` passed and rebuilt `static/css/home-guidance.css`; the home stylesheet cache version was updated.
- Read-only Chrome checks passed at 1440px and 390px for light, dark, light with high contrast and dark with high contrast. All five cards remained responsive with no horizontal overflow.
- Measured title, excerpt, detail, action and icon contrast in default and hovered states met 4.5:1. The minimum recorded default text contrast was 4.53:1.
- Keyboard focus kept visible outlines and revealed details. Touch devices retained readable expanded details.
- Changing dark mode and high contrast through the existing Display controls updated card colors immediately, including high contrast taking precedence over dark mode.
- Browser forced-colors mode retained readable text. No JavaScript errors occurred.
- Light, dark, high-contrast desktop and mobile screenshots were visually inspected. Fixed navigation/display controls are hidden only during section screenshots.
- `git diff --check` passed. The retained local server was restarted with the updated stylesheet and templates. No forms were submitted or messages sent.

`results.json` records the browser measurements. The screenshots in this directory replace the initial palette previews; previous validation artifacts remain as historical evidence.
