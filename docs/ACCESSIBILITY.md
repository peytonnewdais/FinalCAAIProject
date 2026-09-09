# Accessibility

Target: **WCAG 2.1 Level AA**. This document records what was measured, what was changed, and
what is still imperfect. The user-facing version of it is the app's own `/accessibility` page.

The point of writing the numbers down is that they are checked automatically. `tests/test_a11y.py`
recomputes every contrast ratio and colour-blindness separation from the actual palette values, so
a future colour change that breaks a threshold fails the test run rather than shipping quietly.

```bash
pytest tests/test_a11y.py -v
```

## What the audit found

The starting point was not as good as the code comments claimed. The original palette comment said
it had been "run through the dataviz palette validator (CVD separation, lightness band, contrast)".
Measured, it had not been:

| Problem | Was | Now |
|---|---|---|
| Light chart colours below the 3:1 non-text minimum | 3 of 8 (worst 2.11:1) | all ≥ 3:1 |
| `--muted` text (tile labels, table headers, chart tick labels) | 3.41:1 | 4.56:1 |
| `--accent` link text | 4.30:1 | 4.63:1 |
| White text on the light primary button | 4.42:1 | 4.75:1 |
| White text on the **dark** primary button | 3.64:1 | 5.34:1 (near-black ink instead) |
| Active nav link text on its tinted pill | 3.96:1 | 16:1 (ink + underline) |
| Form control and button outlines | ~1.3:1 | ≥ 3:1 (`--border-strong`) |
| `<html lang>` | missing | `en` |
| Focus indicator | none anywhere | 3px ring, ≥ 3:1 |
| Duplicate `contentinfo` landmark | 2 `<footer>` elements | 1 |
| Chart text alternative | none | written summary per figure |

The dark primary button is the interesting one. White-on-accent needs the accent's luminance
≤ 0.183, while accent-as-link-text on the dark page needs ≥ 0.223. No single blue satisfies both,
so dark mode puts near-black ink on the accent fill instead of chasing a compromise colour.

## Colourblind mode

An 8-colour categorical palette cannot be made safe for colour blindness by picking nicer hues.
Measuring the Okabe-Ito palette - the standard CVD-safe reference set - makes the ceiling obvious:

| Palette | normal | protanopia | deuteranopia | tritanopia | contrast floor |
|---|---|---|---|---|---|
| Okabe-Ito (reference) | 21.7 | 10.2 | 13.5 | **1.1** | **1.29:1** |
| Default palette (light) | 13.3 | 1.5 | 1.4 | 0.8 | 3.08:1 |
| **Colourblind mode (light)** | 21.0 | 12.6 | 12.3 | 9.4 | 3.21:1 |
| **Colourblind mode (dark)** | 21.9 | 22.2 | 21.4 | 15.3 | 3.20:1 |

(CIEDE2000 distance between the closest pair of series after simulating each vision type. Below
about 10, two series read as the same colour.)

So colourblind mode does two things, and the second matters more than the first:

1. **A different palette.** Hues sit near eight evenly spaced anchors so it still looks designed,
   but lightness and chroma were optimised to maximise the worst-case separation subject to every
   colour clearing 3:1 on its surface. Lightness does most of the work, because lightness is the
   one channel every form of colour blindness preserves. This beats the reference palette on
   tritanopia (9.4 vs 1.1) and on contrast, which is why it is not simply Okabe-Ito.
2. **Shape, not just colour.** Every industry gets its own dash pattern, and markers get distinct
   symbols. A line stays identifiable with hue removed entirely - which is the actual WCAG 1.4.1
   requirement, and the only honest answer for eight categories.

The default palette is deliberately *not* CVD-optimised. It is tuned for contrast and for the
project's visual identity, and colourblind mode is one click away in the header.

## Success criteria addressed

| SC | Level | How |
|---|---|---|
| 1.1.1 Non-text Content | A | Every Plotly figure has a `<figcaption>` written summary, regenerated whenever the chart updates. Decorative glyphs (brand mark, swatches, card icons) are `aria-hidden`. |
| 1.3.1 Info and Relationships | A | Landmarks for header/nav/main/footer, one `<h1>` per page, `<th scope="col">` on every table, `<caption>` naming each data table, control groups named via `role="group"` + `aria-labelledby`. |
| 1.4.1 Use of Color | A | Gains/losses carry a `+`/`-` sign; the current nav item has a pill, an underline and hidden text; colourblind mode adds dash patterns. |
| 1.4.3 Contrast (Minimum) | AA | All text ≥ 4.5:1, verified live in the DOM and by unit test. |
| 1.4.4 Resize Text | AA | `html` keeps the browser's font size; the design's ratio is set in `rem` on `body`. No `user-scalable=no`. |
| 1.4.10 Reflow | AA | Single-column breakpoints down to 320px; wide tables scroll inside their own container. |
| 1.4.11 Non-text Contrast | AA | Chart series, control outlines and the focus ring all ≥ 3:1. |
| 2.1.1 Keyboard | A | All controls are native or Dash components that are keyboard-operable. |
| 2.3.3 Animation from Interactions | AAA | `prefers-reduced-motion` drops transitions and the card lift. |
| 2.4.1 Bypass Blocks | A | "Skip to main content" is the first tab stop. |
| 2.4.2 Page Titled | A | Each page registers its own `<title>`. |
| 2.4.7 Focus Visible | AA | 3px `:focus-visible` ring, never `outline: none`. |
| 2.5.3 Label in Name | A | Both toggles carry their state in the visible label, so the accessible name matches. |
| 3.1.1 Language of Page | A | `<html lang="en">` via a custom `index_string`. |
| 4.1.3 Status Messages | AA | Errors use `role="alert"`; completed analyses and mode changes use polite live regions. |

Windows High Contrast mode is handled separately with a `forced-colors` block, since the OS
replaces the palette and any border defined only by a custom property would disappear.

## Known limitations

- **Plotly charts.** They can be focused and their toolbar is reachable, but reading individual
  data points by keyboard is limited by Plotly itself. The written summary under each chart and
  the data tables on the Compare and Forecast pages are the reliable route to the same numbers.
- **Generated text.** The Claude-written summaries are labelled as such, but their reading level
  is not controlled and they can be longer than the surrounding page.
- **Not audited by a real screen reader user.** Checks were done with automated measurement plus
  manual keyboard and screen reader passes. That is not the same as testing with people who rely
  on this daily, and it is the obvious next step.

## How the numbers were produced

`services/a11y.py` holds the maths, so the app and the tests share one implementation:

- WCAG relative luminance and contrast ratio (IEC 61966-2-1).
- sRGB ↔ CIE Lab, and CIEDE2000 (Sharma, Wu & Dalal 2005) for perceptual distance.
- Dichromacy simulation via the LMS projection of Viénot, Brettel & Mollon (1999).

Contrast figures quoted above were also confirmed against the live DOM in Chrome, reading the
computed colours off rendered elements rather than trusting the stylesheet.

AI usage: see [AI_USAGE.md](AI_USAGE.md).
