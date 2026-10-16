---
name: Quill
description: A warm-paper reading workbench for source-grounded documents
colors:
  accent: "#28644e"
  accent-hover: "#1c4e3b"
  ink: "#20332e"
  muted: "#66736b"
  olive-text: "#68765d"
  reading-text: "#536b43"
  paper: "#fffefa"
  ground: "#f5f5ef"
  line: "#e0e5dc"
  sidebar: "#172e28"
  sidebar-text: "#d3dfd5"
  nav-selected: "#dce8ca"
  action-text: "#fffdf3"
  danger: "#9d3a33"
  danger-soft: "#fcf0ec"
  focus: "#7aab8e"
typography:
  wordmark:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "31px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "28px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.02em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    lineHeight: 1.65
  reading:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "13px"
    lineHeight: 2.15
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
    fontWeight: 550
    lineHeight: 1.5
rounded:
  compact: "4px"
  small: "5px"
  control: "6px"
  navigation: "7px"
  identity: "8px"
  panel: "9px"
spacing:
  inline: "7px"
  control: "8px"
  compact: "12px"
  gutter: "16px"
  panel: "20px"
  section: "25px"
  shell: "30px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.action-text}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "#3d5241"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "#3d5241"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-danger:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    rounded: "{rounded.control}"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 11px"
  nav-active:
    backgroundColor: "{colors.nav-selected}"
    textColor: "#203d2b"
    rounded: "{rounded.navigation}"
    padding: "11px 12px"
  panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.panel}"
---

# Design System: Quill

## Overview

**Creative North Star: "The Reading Workbench"**

Quill places warm working paper beside a deep green navigation rail. The mood is calm, literate and compact: muted olive metadata supports deep ink titles, while green identifies actions and the current working context. The small serif wordmark provides the literary cue; Chinese working text uses the platform sans stack.

This system records the approved reading-workbench replacement as implemented in the shared shell and knowledge surface. It is extracted from App.vue, workbench.css and knowledge.css, including their final cascade overrides. Knowledge inspection is its first expression; collection widths and preview behavior below describe that expression rather than a mandatory composition for every page. Inherited template/create screens retain scoped treatments and have not all been redesigned.

**Key Characteristics:**

- Warm paper surfaces and a deep ink-green app rail.
- Compact, rule-separated information with restrained rounded containers.
- Chinese sans reading text, a serif wordmark and Lucide line icons.
- Selected-source context and keyboard focus remain visibly distinct.

## Colors

The palette combines green action and navigation with warm neutrals and olive reading support. The frontmatter is the normative value table; CSS custom properties in `workbench.css` supply the shared runtime colors.

### Primary

- **Working Green** (`accent`, `accent-hover`): primary actions, ready states and the caret. Hover deepens the action without adding elevation.

### Neutral

- **Deep Ink** (`ink`): shared foreground and working headings.
- **Warm Paper** (`paper`) and **Workbench Ground** (`ground`): the reading surface and the space around it.
- **Fine Rule** (`line`): shell boundaries, panel borders and internal division.
- **Deep Navigation** (`sidebar`, `sidebar-text`): the app rail and its quiet foreground. **Pale Leaf** (`nav-selected`) identifies the active destination.
- **Muted Text** (`muted`): shared secondary copy. **Olive Text** (`olive-text`) is the final knowledge metadata color; **Reading Olive** (`reading-text`) is the source preview prose.
- **Warm Action White** (`action-text`): primary button text.
- **Focus Green** (`focus`): the shared keyboard outline.

Destructive actions use `danger` and `danger-soft`. The model-configuration indicator uses shell-specific brown and gold before switching to primary green when ready. These semantic colors are status vocabulary, not extra brand accents.

**The Quiet Paper Rule.** Use green for action and selection, and warm paper for sustained reading. Metadata uses the final olive-text treatment rather than the older pale olive declarations earlier in the stylesheet.

## Typography

**Wordmark Font:** Georgia with Times New Roman and serif fallbacks.
**Working Font:** the platform sans stack recorded in the frontmatter, including PingFang SC and Microsoft YaHei for Chinese.

The wordmark adds a small literary accent. Headings, compact controls and long source text remain practical sans text. No web font or raster wordmark is shipped.

- **Wordmark:** the `wordmark` role; mobile reduces it to 25px.
- **Headline:** the `headline` role for the knowledge page heading; mobile uses 25px. Legacy shared workspace headings use 27px and 24px on mobile.
- **Title:** the `title` role for the library heading; compact preview-open layout uses 17px, mobile 18px. Preview titles use 19px, weight 550 and line-height 1.6.
- **Body:** the `body` role is the global baseline. The knowledge workbench deliberately uses smaller sizes for dense controls and metadata.
- **Reading:** the `reading` role is the final source-prose treatment at desktop and mobile. Search-result excerpts use 12px with line-height 1.95; generated answers use 13px with line-height 1.95.
- **Label:** the `label` role describes standard buttons. Resource names and collection labels finish at 13px/550 on desktop and 12px on mobile; secondary resource text finishes at 11px and 10px respectively. Some tertiary metadata remains 9–10px in this build; that is a local density detail, not a new global text baseline.

**The Working Text Rule.** Keep the serif face in the wordmark. Use the platform sans stack for Chinese headings, controls and source text; preserve the reading role when density increases.

## Layout

The shell uses a sticky full-height app rail (208px), a top workspace bar (65px), and a flexible content frame with desktop padding of 29px 30px 36px. Beyond 1800px, content is capped at 1680px. Spacing is compact: seven- to twelve-pixel inline gaps, sixteen- to twenty-five-pixel panel spacing, and thirty-pixel shell gutters recur without forming a strict mathematical scale.

The knowledge reference surface has a collection rail (190px), flexible library panel and a gap (23px). With preview open at widths from 1200px, it uses 170px / flexible / 340px columns and a 17px gap. From 1600px, this becomes 190px / flexible / 390px with a 23px gap. The source panel is sticky (24px top) and its prose scrolls within the viewport-height limit. These measurements belong to knowledge inspection, not all future workspaces.

Between 641px and 1199px, the collection rail is 160px and the preview floats at the right (380px wide, 20px from the right and bottom, 100px from the top). The app rail becomes an icon rail (72px) only between 641px and 1050px.

At 640px and below, the app rail becomes a top masthead and four-column navigation row. The workspace bar is 46px tall; content uses 22px 16px 30px padding. Collections become horizontally scrollable choice chips. The preview replaces the list and collection region with a full-width reading surface; it returns to document flow rather than remaining fixed. Optional table columns disappear, long titles wrap, and actions can wrap. This preserves the source/list relationship without forcing three columns into a narrow viewport.

## Elevation & Depth

Tonal separation and fine one-pixel borders provide ordinary structure. Library and desktop preview panels have no shadow. The connection settings popover uses `0 15px 40px #11251b24`; the intermediate-width floating preview uses `-12px 15px 40px #22331b1a`. These soft shadows clarify overlapping surfaces.

**The Flat Workbench Rule.** Keep ordinary library and preview surfaces flat with fine borders. Reserve soft shadows for the connection popover and the intermediate-width floating preview.

## Shapes

Small, quiet curves organize the workbench: panels and popovers use the panel radius, controls use the control radius, navigation uses the navigation radius, and small icon buttons use the small radius. The mobile collection choices remain gently rounded rectangles rather than pills. Fine rules divide table rows, tabs, facts and reading sections. Circular status dots convey state; file-type tiles use compact rectangular silhouettes. Lucide outline icons are used throughout the redesigned shell and knowledge surface, typically with 1.5–1.7px strokes.

## Components

### Buttons

Primary actions use Working Green, Warm Action White, a one-pixel matching border, the control radius, and the standard button padding. Secondary actions use Warm Paper and a muted green border. Ghost actions remove the border and fill; text actions use green with an underline on hover. Small buttons reduce to a 31px minimum height, 5px 10px padding and 11px text. Disabled buttons use 0.52 opacity and a not-allowed cursor. Standard state transitions last 150ms. Destructive actions use the red semantic pair and explicit confirmation where the current flow supplies it.

### Inputs / Fields

Shared fields use Warm Paper, deep ink text, a fine green-gray border, the control radius and the field padding. The field border deepens on focus. Search uses an icon/input group with a whole-container `focus-within` outline; retrieval has its own slightly softer outline. Keep the global 3px keyboard outline with a 3px offset on ordinary interactive elements. Do not treat the input’s removed internal outline in a grouped search field as permission to remove the group’s visible focus treatment.

### Navigation / Collection Choices

Navigation uses the deep rail, icon-plus-label links and a pale-leaf active row with dark text. Hover uses a quieter green fill. Mobile moves the same destinations into a top row. Collection choices use a soft green selected fill, a fine border and an arrow on desktop; they become compact horizontal choices on mobile. Selected collection is expressed with `aria-pressed`, and library tabs carry selected and keyboard states.

### Cards / Containers

Library and preview share Warm Paper, the panel radius and a Fine Rule border. Internal sections use padding and horizontal rules rather than nested elevated cards. The source-answer block uses a restrained pale green fill and border. Empty and loading states occupy the same working panel, with short explanatory copy and a relevant action.

### Resource Row / Source Preview

Resource rows combine a file-type tile, wrapping source title, secondary provenance text, status and optional facts. Hover and active-source fills differ subtly. Retrieval results expose a source link and excerpt with matching-term highlights. Opening the source moves focus to its close action; closing restores the triggering control, or the active library tab if that control is gone. Escape also closes the preview. The preview is an adjacent reading region, not a modal dialog with a focus trap.

The preview enters over 220ms with an 8px horizontal move and a small brightness adjustment. The shared reduced-motion query removes animations and transitions. Original text preserves whitespace and wraps long content. Reading segments are explicitly labeled as a browsing aid; status labels must distinguish saved text from actual vector readiness.

## Do's and Don'ts

### Do:

- **Do** use the shared paper, ground, ink and green action roles when adding a surface.
- **Do** preserve visible keyboard focus, the reduced-motion override and the source preview’s focus restoration.
- **Do** use line icons with visible labels or accessible names; preserve readable Chinese source titles and wrapping.
- **Do** keep the original text and source metadata available beside or in place of the resource list as space permits.

### Don't:

- **Don’t** introduce a new display face for working text; the serif wordmark already supplies the typographic contrast.
- **Don’t** use the inherited template pages’ emoji icons or blue glow shadows as patterns for new workbench components.
- **Don’t** add shadows to every container; use border and surface tone for resting structure.
- **Don’t** present reading segments, vector readiness, counts or answers as decoration; their labels and states must follow actual data.

Not canonized: inherited template/create screens still carry emoji icons, larger scoped type and blue glow shadows. They remain migration drift outside the redesigned shell and knowledge system; this documentation pass does not repair them. No shipped raster assets belong to this visual world.
