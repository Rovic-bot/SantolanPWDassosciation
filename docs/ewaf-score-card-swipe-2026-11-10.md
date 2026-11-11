# Swipe between member score breakdowns

## Current behavior: update applicants without rebuilding the page

The full-screen blink came from the shared navigation replacing the body contents and reinitializing styles, scripts, theme controls, and the deck on every applicant change. Same-program, same-calculation responses now use an in-place renderer after the ordinary authenticated GET and response checks. The shell, sidebar, page header, filter controls, score-card element, and criterion box stay mounted; there is no stylesheet/script reload or theme reinitialization. Unsupported responses and different pages/calculations retain normal navigation.

Fresh server-rendered content updates the card, eligibility/ranking notice, calculation metadata/details, comparison selection, and saved-calculation options. Open disclosures and table scroll positions are preserved. Comparison links, dropdowns, dots, keyboard arrows, mouse/touch swipes, and browser Back/Forward use the same renderer. Card dragging and criterion interpolation remain; the next card is committed at rest without sliding back across the screen. Interpolation continues from currently visible values during rapid switching, and reduced-motion preferences remain respected.

Read-only browser checks using the existing three-member ranking confirmed stable DOM identity for the shell/controls/card/chart, retained head assets, zero stylesheet/script requests after initial loading, preserved disclosure state, synchronized details, directional drag, exact final criterion values, rapid changes, browser history, comparison links, failed-request recovery, mobile touch, dark/high-contrast preferences, and reduced motion. No horizontal overflow or JavaScript errors occurred. Django checks, JavaScript syntax checks, and `git diff --check` passed. No operational writes or database test suites were run. This supersedes the page-replacement implementation described below.

## Previous implementation: card dragging and changing criterion values

The owner clarified that the left card should keep its dragging animation, while the criterion bars and numbers should animate from the current applicant's values to the next applicant's values. Drag-follow, tilt, adjacent-card reveal, snap-back, and card exit motion are restored without delaying the GET request. The page and all surrounding boxes remain stationary.

Before replacing the page, the authorized response receives the currently displayed starting values, matched by criterion code within the same saved calculation. The new member's saved contribution values remain the targets. Bars and visible numbers interpolate together for 360 ms, increasing or decreasing as appropriate, then finish at the exact server-provided values. Rapid changes continue from the visible intermediate values. Screen readers receive the final values directly; site/device reduced-motion preferences skip interpolation, including when changed during an animation. No score computation or stored ranking changes.

Read-only browser checks on the existing three-member ranking confirmed drag and snap-back, mobile touch swiping, immediate navigation, increasing/decreasing values without overshoot, synchronized bars/numbers, exact final values, rapid navigation, failed-request recovery, and both reduced-motion settings. The page/boxes stayed still; no horizontal overflow or JavaScript errors occurred. The drag screenshot was inspected. Django system checks, JavaScript syntax checks, and `git diff --check` passed. No database test suites, synthetic records, or operational writes were run. This supersedes the earlier animation iterations below.

## Previous request: animations removed

At the owner's request, applicant switching now has no card, box, or page animation. Removed sliding, fading, rotation, drag-follow motion, and animation-specific navigation hooks. The static stacked-card appearance, independent box heights, swipe gestures, arrows, dots, and keyboard navigation remain. The current card stays visible until the authorized GET response replaces it.

Read-only browser checks confirmed swipe and keyboard switching with no transform, a zero-second card transition, and zero animation calls or JavaScript errors. Django checks, JavaScript syntax checks, and `git diff --check` passed. No operational data or test fixtures were created. This behavior supersedes the animation descriptions below.

## Follow-up: immediate switching with box animations only

This replaces the earlier full-page animation. Committing a swipe, arrow, or dot now submits the existing authorized GET immediately, without the 180 ms pre-request timer or the 160 ms outgoing-page animation. The fresh response is displayed without hiding the page. Only the score stack, criterion box, calculation details, comparison box, and saved-calculation box receive a concurrent 180 ms entrance animation; the page container, heading, tabs, filters, and navigation remain stationary. Animation completion does not block navigation, and page-scoped cleanup handles quick subsequent changes. The server request is still required to retrieve the current authorized details.

Read-only previews of the existing ranking confirmed synchronous submission, animation targets limited to the five boxes, next/previous direction, keyboard/dropdown/wraparound navigation, mouse swiping, failed-request recovery, both reduced-motion preferences, cleanup, and no mobile horizontal overflow. JavaScript errors: zero. Django checks, JavaScript syntax checks, and `git diff --check` passed. No database test suite, operational writes, or generated records were used.

## Follow-up: independent card heights

The breakdown grid now aligns its boxes at the top without stretching them to a shared height. The visible swipe hint and the member card's minimum height were removed; swipe instructions remain in the card's accessible label, alongside the existing arrows and dots. Swiping and full-page transitions are unchanged.

Read-only browser previews of existing records showed member/criterion card heights of 380/351 px on desktop and 372/360 px on mobile. The hint was absent, applicant navigation worked, and no horizontal overflow or JavaScript errors occurred. Desktop and mobile screenshots were inspected. Django system checks, JavaScript syntax, and `git diff --check` passed; no database test suite or data writes were run.

## Follow-up: animate the complete breakdown

Applicant changes now slide and fade the complete score-breakdown content out and in, including the score card, criterion chart, calculation details, comparison table, and history. Direction follows next/previous navigation, including wraparound. The persistent admin navigation stays in place. The fresh, authorized GET response is prepared before the outgoing animation starts; content remains available if the request fails. The page remains busy until the incoming transition finishes, and reduced-motion settings skip both page animations.

Read-only browser verification using the three existing applicants confirmed full-container outgoing/incoming animations, opposite directions for keyboard navigation, dropdown navigation, last-to-first cycling, browser Back, failed-fetch recovery, and both site/device reduced-motion preferences. The saved calculation stayed unchanged. No mobile horizontal overflow or JavaScript errors occurred. Django system checks, JavaScript syntax checks, and `git diff --check` passed. No database test suite or data generation was run. Static asset versions were updated to load the new behavior after refresh.

## Follow-up: stacked flashcard deck

The owner requested the stacked-deck reference. The active card now follows horizontal pointer movement with a small rotation, revealing a preview of the actual adjacent member. Short gestures snap back; committed gestures slide the card away before the existing authenticated navigation replaces the complete breakdown. Two offset layers, a swipe hint, compact arrows, and up to seven position dots provide the deck presentation. Light, dark, and high-contrast modes use the existing palette. Reduced-motion preferences suppress sliding/rotation transitions.

Preview data contains only the permitted score summary for applicants already listed in that same saved run; no new cross-program or public access is added. Preview content is inert and hidden from assistive technology. A failed GET restores the original card and selected applicant; successful navigation disposes the old event handlers. No eligibility, ranking, selection, or database state changes occur on swiping.

Read-only previews of the existing three-member ranking passed drag/tilt, short-swipe snap-back, next/previous cycling, dots, mobile touch, vertical-scroll preservation, synchronized details, simulated fetch-failure recovery, and reduced-motion navigation. Mobile layout had no horizontal overflow; JavaScript errors: zero. Inspected light, dark, and high-contrast card screenshots. Django checks and source syntax checks passed. No database test suites, fixtures, or operational writes were run. These observations supersede the earlier simple swipe presentation below.

The score summary card now supports left/right swipes, mouse dragging, Previous/Next member buttons, and keyboard arrows. Navigation follows the existing ranked applicant selector and wraps at both ends. The existing authenticated GET form reloads the complete breakdown for the selected member and preserves the saved calculation; no scores or member records are changed.

The card preserves vertical scrolling and pinch zoom. Short or predominantly vertical gestures do not switch members. Controls are hidden when there is only one member, and the original applicant selector remains available without JavaScript. Page-scoped event handlers are cleaned up during workspace navigation.

Validation used read-only renders of the three existing applicants in the current saved ranking, with browser requests restricted to those rendered pages and local static assets. Mouse drag, keyboard navigation, both-end cycling, arrow buttons, mobile touch swiping, unchanged selection on vertical gestures, and synchronized calculation details passed; no page JavaScript errors were observed. Django checks, JavaScript syntax and `git diff --check` passed. No automated database test suite, synthetic records or application writes were used. Private preview artifacts remain in `.local/development/score-swipe/`.
