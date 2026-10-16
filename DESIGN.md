---
name: Quill
description: A shared warm-paper workbench for knowledge, templates and source-grounded writing
colors:
  accent: '#28644e'
  accent-hover: '#1c4e3b'
  ink: '#20332e'
  muted: '#66736b'
  paper: '#fffefa'
  ground: '#f5f5ef'
  line: '#e0e5dc'
  sidebar: '#172e28'
  sidebar-text: '#d3dfd5'
  nav-selected: '#dce8ca'
  action-text: '#fffdf3'
  danger: '#9d3a33'
  danger-soft: '#fcf0ec'
  focus: '#7aab8e'
  accent-soft: '#e6eee6'
  surface-subtle: '#fafbf6'
  amber: '#886222'
  amber-soft: '#f9f1df'
typography:
  wordmark:
    fontFamily: Georgia, 'Times New Roman', serif
    fontSize: 31px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: -0.025em
  headline:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 28px
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: -0.025em
  title:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 19px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: -0.02em
  body:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 14px
    lineHeight: 1.65
  reading:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 15px
    lineHeight: 1.95
  label:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 13px
    fontWeight: 550
    lineHeight: 1.5
  section:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.5
  field:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.65
rounded:
  compact: 4px
  small: 5px
  control: 6px
  navigation: 7px
  identity: 8px
  panel: 9px
spacing:
  space-1: 4px
  space-2: 8px
  space-3: 12px
  space-4: 16px
  space-6: 24px
  space-8: 32px
components:
  button-primary:
    backgroundColor: '{colors.accent}'
    textColor: '{colors.action-text}'
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 9px 14px
  button-primary-hover:
    backgroundColor: '{colors.accent-hover}'
  button-secondary:
    backgroundColor: '{colors.paper}'
    textColor: '#3d5241'
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 9px 14px
  button-ghost:
    backgroundColor: transparent
    textColor: '#3d5241'
    rounded: '{rounded.control}'
    padding: 9px 14px
  button-danger:
    backgroundColor: '{colors.danger-soft}'
    textColor: '{colors.danger}'
    rounded: '{rounded.control}'
  field:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 9px 11px
    typography: '{typography.field}'
  nav-active:
    backgroundColor: '{colors.nav-selected}'
    textColor: '#203d2b'
    rounded: '{rounded.navigation}'
    padding: 11px 12px
  panel:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.panel}'
  button-small:
    padding: 5px 10px
    rounded: '{rounded.control}'
  editor-aside:
    backgroundColor: '{colors.surface-subtle}'
    textColor: '{colors.muted}'
    padding: 28px 24px
---

# Design System: Quill

## Overview

**Creative North Star: "The Reading Workbench"**

Quill places warm working paper beside deep green navigation. The mood is calm, literate and practical: deep ink carries source text and headings, neutral muted text carries supporting information, and green identifies actions and the current working context. The small serif wordmark provides the literary cue; Chinese working text uses the platform sans stack.

The confirmed reading-workbench world now spans knowledge management, source inspection, writing, template browsing, template upload and template-based generation. Shared controls, fine rules and restrained surfaces give the whole working path one vocabulary. This record is extracted from App.vue and the workbench, knowledge and documents stylesheets, including their final responsive overrides. The reference-driven refinement changes readability and consistency within that world; it does not import another product’s brand.

**Key Characteristics:**

- Warm paper and subtle neutral surfaces beneath a deep green app rail.
- Ink reading text, muted metadata and green action/selection states.
- Shared control sizes, fine rules and restrained rounded containers across all flows.
- Chinese sans working text, a small serif wordmark and Lucide line icons.

## Colors

Warm paper, deep green navigation and ink text establish the workbench. The frontmatter is the normative token table. Shared runtime color custom properties live in `workbench.css`; small shell-specific color treatments remain local. Sidecar tonal ramps are synthesized display aids, not additional runtime colors.

### Primary

- **Working Green** (`accent`, `accent-hover`): primary actions, ready states and the caret. Hover deepens the action without elevation.
- **Soft Green** (`accent-soft`): selected catalog categories, completed jobs, indexed status and upload hover feedback.

### Neutral

- **Deep Ink** (`ink`): working headings, resource titles, original text, excerpts and generated prose.
- **Muted Neutral** (`muted`): provenance, secondary labels, counts, helper copy and metadata. The previous olive reading and pale metadata treatments have been replaced.
- **Warm Paper** (`paper`), **Subtle Surface** (`surface-subtle`) and **Workbench Ground** (`ground`): main panels, supporting regions such as editor asides, and the space around panels.
- **Fine Rule** (`line`): panel edges, row boundaries and internal divisions.
- **Deep Navigation** (`sidebar`, `sidebar-text`): the app rail and its quiet foreground. **Pale Leaf** (`nav-selected`) identifies the active destination.
- **Warm Action White** (`action-text`): primary button text.
- **Focus Green** (`focus`): the shared keyboard outline.

Destructive actions use `danger` and `danger-soft`. Interrupted or failed generation jobs use `amber` and `amber-soft`; model configuration retains a small shell-specific brown/gold indicator until ready. Semantic warning and destructive colors do not become extra brand accents.

**The Quiet Paper Rule.** Use ink for sustained reading and muted neutral text for metadata. Reserve green for actions, readiness and selection; keep warm paper as the working surface.

## Typography

**Wordmark Font:** Georgia with Times New Roman and serif fallbacks.
**Working Font:** the platform sans stack in the frontmatter, including PingFang SC and Microsoft YaHei for Chinese.

The wordmark adds a small literary accent. Working text uses practical sans hierarchy with a consistent readable source scale. No web font or raster wordmark is shipped.

- **Wordmark:** the `wordmark` role; mobile reduces it to 25px.
- **Headline:** the `headline` role for page headings; mobile uses 25px.
- **Title:** the `title` role for the library heading; the inline-preview layout uses 17px and mobile uses 19px. Source-preview titles use 20px, weight 550 and line-height 1.6.
- **Section:** the `section` role for document editor sections and aside headings. Catalog titles use 16px, weight 550 and line-height 1.6, increasing to 17px on mobile.
- **Body:** the `body` role is the global baseline. Resource titles and collection labels use 14px/550 on desktop and 13px on mobile. Resource metadata is 12px. Page introductions use 14px/1.9 on desktop and 13px on mobile.
- **Reading:** the `reading` role is shared by original source prose, answers and generated document text. Source prose is limited to 75ch; generated prose to 78ch. Search excerpts use 14px/1.9.
- **Label:** the `label` role describes standard buttons. Small buttons use 12px. Shared fields use 14px regular text on desktop and 16px on mobile. Metadata and document help are usually 12–13px; small 9–11px brand and file-format details are local annotations rather than a working-text baseline.

**The Working Text Rule.** Keep the serif face in the wordmark and use the platform sans stack for Chinese work. Source prose and generated document prose share the 15px reading role with line-height 1.95.

## Layout

The shell uses a sticky full-height app rail (208px), a workspace bar (65px), and a flexible content frame with padding of 29px 30px 36px. Above 1800px, content is capped at 1680px. Document workspaces are capped at 1280px. The shared spacing custom properties are the `space-*` entries in the frontmatter: a four-pixel foundation through 32px. The implemented layouts also retain intermediate spacing for specific information groups; the tokens describe a working rhythm rather than an enforced grid for every measurement.

The knowledge reference surface uses a collection rail (190px), flexible library panel and a 23px gap. With preview open from 1360px, it uses 176px / flexible / 380px columns with a 17px gap. From 1600px, this becomes 190px / flexible / 420px with a 23px gap. The source panel is sticky, 24px from the top, with a maximum height of `calc(100dvh - 112px)` and an independently scrolling prose region.

Between 641px and 1359px, the collection rail is 160px and the preview floats 20px from the right and bottom and 100px from the top. Its final width is `min(440px, calc(100vw - 110px))`; this overrides the earlier fixed-width declaration. The app rail becomes an icon rail (72px) only between 641px and 1050px.

Document editing uses a flexible main region with a 300px supporting aside, divided by a rule inside one paper panel. At 1100px and below, the aside becomes 260px and variable fields move from two columns to one. At 800px and below, the aside stacks below the main region. The catalog changes from three equal columns to two at 1100px and one at 640px; its alternative list view keeps document context and actions together.

At 640px and below, the app rail becomes a top masthead and four-column navigation row. The workspace bar is 46px tall; content uses 22px 16px 30px padding. Collections become horizontal choices. Source preview replaces the list and collection region with full-width reading content in document flow. Optional table columns disappear, filters and actions wrap, and file-type tiles are hidden to protect title space. Document forms, variable entry and submit controls stack; catalog rows become one-column entries.

## Elevation & Depth

Tonal separation and one-pixel borders provide ordinary structure. Library, document editor, catalog and inline source panels have no shadow. The connection popover uses `0 15px 40px #11251b24`; the intermediate-width floating preview uses `-12px 15px 40px #22331b1a`. A one-pixel inset-like line beneath an active import method is an indicator, not container elevation.

**The Flat Workbench Rule.** Keep ordinary library, editor, catalog and inline preview surfaces flat with fine borders. Reserve soft shadows for the connection popover and the intermediate-width floating preview.

## Shapes

The form language is restrained and rectangular. Shared controls use `radius-control`; shared panels and document editors use `radius-panel`. Compact status labels and document-sheet motifs use the compact radius. Navigation rows and grouped view controls use the navigation radius. One-pixel rules divide rows, tabs, editor sections and catalog entries. Horizontal collection choices remain gently rounded rectangles rather than pills.

Lucide outline icons replace the old template emoji and support all working flows. Typical icons are 15–24px with restrained strokes; the wordmark and small identity initial carry the serif detail. Template-sheet motifs are CSS-and-SVG document cues, not thumbnail images.

## Components

### Buttons

Standard buttons use a 40px minimum height, 9px 14px padding, the control radius and the label role. Primary actions use Working Green and Warm Action White; hover deepens the green. Secondary actions use Warm Paper and a fine green-gray border. Ghost actions remove the resting fill and border. Destructive actions use the semantic red pair. Text actions use green and gain an underline on hover. Small buttons use a 34px minimum height, 5px 10px padding and 12px text. Disabled buttons use 0.52 opacity and a not-allowed cursor. Ordinary state transitions last 150ms.

At mobile widths, standard buttons have a 44px minimum height and small buttons a 40px minimum. Shared icon buttons move from 34px square to 40px square. Some inline knowledge edit and dismiss controls retain compact local overrides; those exceptions do not redefine shared button sizes. The mobile retrieval submit uses a 44px minimum height and 13px text, and its option selects use a 40px minimum height.

### Inputs / Fields

Shared fields use Warm Paper, deep ink text, a fine green-gray border, the control radius and 9px 11px padding. They use regular weight (400), 14px text and a 40px minimum height on desktop, 16px text and a 44px minimum height on mobile. The border deepens on focus. Grouped catalog search uses Subtle Surface and a whole-container focus outline; knowledge filters and retrieval have their own group outlines. A removed internal input outline must retain the visible group focus treatment.

The global keyboard outline is 3px with a 3px offset. Catalog search uses the same width with a 2px offset; knowledge group outlines use 2px. Template upload shows focus around the whole drop region. Visible field labels remain outside the input. Long references, outlines and variable fields support normal wrapping or resizing appropriate to their control.

### Navigation / Choices / Status

App navigation uses the deep rail, icon-plus-label links and a pale-leaf active row with dark text. Desktop links use 14px text; mobile destinations use compact labels and a minimum height of 42px. Collection choices use a soft green selected fill, border and desktop arrow; selected choices use ink text and `aria-pressed`. Catalog categories use green text and Soft Green for their pressed state. Library tabs expose selected and keyboard states.

Index and generation status labels use compact rectangular shapes. Neutral status uses a subtle fill; indexed or completed status uses Soft Green with green text. Warning status uses the amber pair. Status combines text and state treatment rather than depending on a colored dot alone.

### Cards / Containers / Catalog Entries

Library, preview, catalog and document editor share Warm Paper, a fine border and restrained panel corners. Document asides use Subtle Surface and a dividing rule. Internal sections use padding and rules rather than nested shadows. Catalog entries use a document-sheet cue, category, wrapping title, description and conventional linked actions. Grid and list views share that content hierarchy. Empty and loading states occupy the same panel and explain the next useful action.

### Resource Row / Source Preview / Generated Text

Resource rows combine a wrapping source title, secondary provenance and a text readiness label. Hover and active-source fills differ subtly; source-title hover adds an underline. Retrieval results expose a linked source and excerpt with matching-term highlights. Opening a source moves focus to its close action; closing restores the trigger or the active library tab if the trigger is gone. Escape closes the preview. It remains an adjacent reading region rather than a modal focus trap.

Source prose and generated prose use the reading role, preserve whitespace and wrap long content. Source reading segments remain explicitly labeled as browsing aids. The preview enters over 220ms with an 8px horizontal move and a slight brightness change. The shared reduced-motion query removes animations and transitions. Document generation history and download regions use the same paper, ink, muted and green vocabulary as source inspection.

## Do's and Don'ts

### Do:

- **Do** use shared paper, subtle-surface, ink, muted and green action roles across knowledge and document flows.
- **Do** preserve the 15px reading role and distinguish supporting metadata through hierarchy rather than pale text.
- **Do** use shared button and field primitives, with the explicit mobile sizing and responsive layout rules.
- **Do** preserve visible keyboard focus, reduced-motion support and source preview focus restoration.
- **Do** use Lucide line icons with visible labels or accessible names, wrapping long Chinese titles and source text.

### Don't:

- **Don’t** introduce a new display face for working text; the serif wordmark already supplies typographic contrast.
- **Don’t** restore emoji iconography, blue glow shadows or decorative gradients from the replaced template interface.
- **Don’t** add shadows to every container; use border and surface tone for resting structure.
- **Don’t** present reading segments, index readiness, counts or answers as decoration; their labels and states must follow actual data.

Not canonized: scoped compact knowledge actions remain smaller than the shared control primitives; record their current behavior without making them a new default. The old template/create emoji, blue gradients and glow shadows have been removed, so they are no longer migration drift. No shipped raster assets belong to this system.
