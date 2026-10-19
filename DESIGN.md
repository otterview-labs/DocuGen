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
  line-strong: '#cbd6c9'
  hover: '#f0f4e9'
  highlight: '#e5edbe'
  brand-symbol: '#dce8b6'
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
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.025em
  title:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 20px
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
    fontWeight: 500
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
    lineHeight: 1.5
  meta:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.65
rounded:
  tag: 4px
  control: 6px
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
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 0 14px
    height: 40px
    backgroundColor: '{colors.accent}'
    textColor: '{colors.action-text}'
  button-primary-hover:
    backgroundColor: '{colors.accent-hover}'
  button-secondary:
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 0 14px
    height: 40px
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
  button-ghost:
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 0 14px
    height: 40px
    backgroundColor: transparent
    textColor: '{colors.muted}'
  button-text:
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: '0'
    height: 32px
    backgroundColor: transparent
    textColor: '{colors.accent}'
  button-danger:
    typography: '{typography.label}'
    rounded: '{rounded.control}'
    padding: 0 14px
    height: 40px
    backgroundColor: '{colors.danger-soft}'
    textColor: '{colors.danger}'
  button-compact:
    typography: '{typography.label}'
    height: 32px
    padding: 0 10px
    rounded: '{rounded.control}'
  button-pressed:
    backgroundColor: '{colors.accent-soft}'
    textColor: '{colors.accent}'
  field:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    typography: '{typography.field}'
    rounded: '{rounded.control}'
    padding: 9px 11px
    height: 40px
  file-picker:
    backgroundColor: '{colors.surface-subtle}'
    textColor: '{colors.accent}'
    rounded: '{rounded.control}'
    padding: 20px
  nav-active:
    backgroundColor: '{colors.nav-selected}'
    textColor: '#203d2b'
    rounded: '{rounded.control}'
    padding: 11px 12px
  panel:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.panel}'
  notice:
    backgroundColor: '{colors.surface-subtle}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 14px 16px
  editor-aside:
    backgroundColor: '{colors.surface-subtle}'
    textColor: '{colors.muted}'
    padding: 28px 24px
---

# Design System: Quill

## Overview

**Creative North Star: "The Reading Workbench"**

Quill places warm working paper beside deep green navigation. The mood is calm, literate and practical: deep ink carries source text and headings, neutral muted text carries supporting information, and green identifies actions and the current working context. The small serif wordmark provides the literary cue; Chinese working text uses one platform sans family.

The reading-workbench world spans knowledge management, source inspection, writing, template browsing, upload and template-based generation. Its visual primitives now have one canonical owner: ui.css and the shared UiButton, UiPageHeader, UiNotice, UiEmptyState, UiTabs and UiFilePicker components. Workbench, knowledge and document styles arrange these primitives and define deliberate reading or content-title roles. This record follows the actual component rules and computed-style reports at 1440px, 1024px and 390px; the confirmed visual identity is preserved.

**Key Characteristics:**

- Warm paper and subtle neutral surfaces beneath deep green navigation.
- One working font family, semantic type roles and consistent action geometry.
- Ink reading text, muted metadata and green action/selection states.
- Shared buttons, page headers, notices, empty states, keyboard tabs and native file selection across all flows.

## Colors

Warm paper, deep green navigation and ink text establish the workbench. The frontmatter is the normative token table. Palette and shell colors live in `workbench.css`; `ui.css` owns the shared semantic control, typography, focus and highlight tokens. Small navigation-specific treatments remain local. Sidecar tonal ramps are synthesized display aids, not additional runtime colors.

### Primary

- **Working Green** (`accent`, `accent-hover`): primary actions, ready states and the caret. Hover deepens the action without elevation.
- **Soft Green** (`accent-soft`): selected catalog categories, completed jobs, indexed status and upload hover feedback.

### Neutral

- **Deep Ink** (`ink`): working headings, resource titles, original text, excerpts and generated prose.
- **Muted Neutral** (`muted`): provenance, secondary labels, counts, helper copy and metadata. The same roles apply to controls, source content and document workflows.
- **Warm Paper** (`paper`), **Subtle Surface** (`surface-subtle`) and **Workbench Ground** (`ground`): main panels, supporting regions such as editor asides, and the space around panels.
- **Fine Rule** (`line`) and **Control Rule** (`line-strong`): panel/internal divisions and shared control borders. **Control Hover** (`hover`) supplies the quiet action hover fill.
- **Deep Navigation** (`sidebar`, `sidebar-text`): the app rail and its quiet foreground. **Pale Leaf** (`nav-selected`) identifies the active destination.
- **Warm Action White** (`action-text`): primary button text.
- **Focus Green** (`focus`): the shared keyboard outline. **Source Highlight** (`highlight`) marks matching text while retaining ink foreground. **Brand Feather** (`brand-symbol`) belongs to the navigation brand mark.

Destructive actions use `danger` and `danger-soft`. Interrupted or failed generation jobs use `amber` and `amber-soft`; model configuration uses the same amber role until ready. Semantic warning and destructive colors do not become extra brand accents.

**The Quiet Paper Rule.** Use ink for sustained reading and muted neutral text for metadata. Reserve green for actions, readiness and selection; keep warm paper as the working surface.

## Typography

**Wordmark Font:** Georgia with Times New Roman and serif fallbacks.
**Working Font:** `--font-family-working`, defined in `ui.css` and recorded in the frontmatter: the platform sans stack including PingFang SC and Microsoft YaHei. Root text, all native controls and content links inherit it. No web font or raster wordmark is shipped.

The hierarchy distinguishes reading and navigation tasks without changing the action label role between pages or sizes.

- **Wordmark:** 31px/500 on desktop; mobile uses the 24px page-mobile size while retaining the serif face and line-height 1.
- **Headline:** 28px/600 with line-height 1.3; all shared page headers use 24px/600 on mobile.
- **Title:** 20px for library and source titles. Library titles use weight 600 and line-height 1.4; source titles use weight 500 and line-height 1.6. The inline-preview library title steps down to the 16px section size.
- **Section:** 16px/600 for editor and aside headings. Catalog titles use the same size with weight 500 and line-height 1.6 at all breakpoints.
- **Body:** 14px is the global working baseline. Collection labels and source names use weight 500, reducing to the 13px control size on mobile. Page descriptions use 14px/400 with line-height 1.8, then 13px on mobile.
- **Reading:** 15px with line-height 1.95 for original source prose, answers and generated document text. Source prose is capped at 75ch and generated prose at 78ch. Search excerpts use 14px/1.9.
- **Label:** every action label uses 13px/500 and line-height 1.5, including compact and text variants.
- **Field:** 14px/400 with line-height 1.5, increasing to 16px on mobile. Field labels use 13px/600.
- **Metadata:** 12px regular working text for provenance, secondary counts and helper information. File-format and wordmark annotations retain their deliberate local roles.

**The Working Text Rule.** Use the canonical working family for native controls and content links. Preserve semantic differences between page headings, content titles, sections, reading text and labels; every action label uses the same 13px/500 role.

## Layout

The shell uses a sticky full-height app rail (208px), a workspace bar (65px), and a flexible content frame with padding of 29px 30px 36px. Above 1800px, content is capped at 1680px. Document workspaces are capped at 1280px. The shared spacing custom properties are the `space-*` entries in the frontmatter: a four-pixel foundation through 32px. The implemented layouts also retain intermediate spacing for specific information groups; the tokens describe a working rhythm rather than an enforced grid for every measurement.

The knowledge reference surface uses a collection rail (190px), flexible library panel and a 23px gap. With preview open from 1360px, it uses 176px / flexible / 380px columns with a 17px gap. From 1600px, this becomes 190px / flexible / 420px with a 23px gap. The source panel is sticky, 24px from the top, with a maximum height of `calc(100dvh - 112px)` and an independently scrolling prose region.

Between 641px and 1359px, the collection rail is 160px and the preview floats 20px from the right and bottom and 100px from the top. Its final width is `min(440px, calc(100vw - 110px))`; this overrides the earlier fixed-width declaration. The app rail becomes an icon rail (72px) only between 641px and 1050px.

Document editing uses a flexible main region with a 300px supporting aside, divided by a rule inside one paper panel. At 1100px and below, the aside becomes 260px and variable fields move from two columns to one. At 800px and below, the aside stacks below the main region. The catalog changes from three equal columns to two at 1100px and one at 640px; its alternative list view keeps document context and actions together.

At 640px and below, the app rail becomes a top masthead and four-column navigation row. The workspace bar is 46px tall; content uses 22px 16px 30px padding. Collections become horizontal choices. Source preview replaces the list and collection region with full-width reading content in document flow. Optional table columns disappear, filters and actions wrap, and file-type tiles are hidden to protect title space. Document forms, variable entry and submit controls stack; catalog rows become one-column entries.

## Elevation & Depth

Tonal separation and one-pixel borders provide ordinary structure. Library, document editor, catalog and inline source panels have no shadow. The connection popover uses `0 15px 40px #11251b24`; the intermediate-width floating preview uses `-12px 15px 40px #22331b1a`. Shared tabs use a two-pixel selected underline; it is an indicator, not container elevation.

**The Flat Workbench Rule.** Keep ordinary library, editor, catalog and inline preview surfaces flat with fine borders. Reserve soft shadows for the connection popover and the intermediate-width floating preview.

## Shapes

The form language is restrained and rectangular. Shared controls use `control-radius` (with the matching shell `radius-control` alias); shared panels and document editors use `radius-panel`. Compact status labels and document-sheet motifs use the tag radius. Navigation rows also use the control radius. One-pixel rules divide rows, tabs, editor sections and catalog entries. Horizontal collection choices remain gently rounded rectangles rather than pills.

Lucide outline icons replace the old template emoji and support all working flows. Action and tab icons use exactly 16px with 1.75 stroke width. Empty-state icons use 32px/1.6 and upload icons use 26px/1.6, preserving their different roles; the wordmark and small identity initial carry the serif detail. Template-sheet motifs are CSS-and-SVG document cues, not thumbnail images.

## Components

### Shared Ownership

Use `UiButton`, `UiPageHeader`, `UiNotice`, `UiEmptyState`, `UiTabs` and `UiFilePicker` from `frontend/src/components/ui`. Their visual rules live in `frontend/src/styles/ui.css`. Page styles arrange shared controls without redefining their typography, colors, shape or geometry. App navigation, source titles, document prose and collection choices retain their intentional content roles. Shared form rows use a 12px gap; the retrieval search group that contains an action uses 8px padding and gap.

### Buttons

`UiButton` renders a native button, RouterLink or anchor with one visual contract. Standard controls are 40px high with 0 14px padding; compact controls are 32px with 0 10px padding. At mobile widths, their heights become 44px and 40px respectively. Icon-only controls are square at the selected size. Every action label stays 13px/500, every action icon is 16px with 1.75 stroke width, and every button uses the 6px control radius.

Secondary buttons use paper, ink and the strong control border. Primary buttons use green and action-white, with both fill and border deepening on hover. Ghost buttons use transparent fill/border and muted text, gaining ink text and the shared hover fill. Text buttons use green with transparent fill/border, zero inline padding and compact height; choosing compact size applies its 10px inline padding. Their hover underlines at a 4px offset. Danger buttons use destructive fill, text and border. Pressed controls use soft green and green text. Disabled controls use 0.5 opacity and a not-allowed cursor. State transitions last 150ms; keyboard focus uses a 3px ring with a 3px offset.

Native `UiButton` defaults to `type="button"`; real form submissions declare `type="submit"` explicitly. Preserve that behavior when adding forms, including connection settings, knowledge import/search and writing.

### Inputs / Search / Upload

Shared fields use paper, ink, a strong one-pixel border, 6px corners and 9px 11px padding. Inputs and selects have the standard control height; textareas have that minimum height and resize vertically. Field text is 14px/400, 16px on mobile; labels are 13px/600. Focus changes the border to green and uses a 3px ring with a 2px offset. Placeholder text uses muted neutral at regular weight.

Grouped search uses the same paper/border geometry, 16px/1.75 icon and an inherited working-family input. Focus surrounds the whole group. Search with an embedded action adds 8px padding and gap. Full upload regions share a dashed strong border, subtle surface, 156px minimum height and centered copy. Hover or dragging uses soft green and a green border; whole-region focus stays visible.

### File Picker

`UiFilePicker` owns compact single-file selection in `frontend/src/components/ui/UiFilePicker.vue`; its visual states belong to `ui.css`. It uses the existing subtle surface, strong dashed border and control radius, with a 104px minimum height, 20px padding and 16px icon-to-copy gap. At 640px and below, these become 100px, 16px and 12px. The leading upload/file icon is 24px with 1.75 stroke width; a selected file adds an 18px check. File names use body-size medium ink text and wrap; hints and formatted sizes use regular metadata text. Hover or drag uses soft green with a green border and green hint text; selection changes the border to solid. Focus within uses the shared 3px ring and 3px offset; disabled selection uses 0.52 opacity and a not-allowed pointer.

The transparent native file input covers the selection region and retains its accessible label, `accept`, `required`, disabled and keyboard behavior. The component exposes a single File or null through `v-model`, shows Chinese selection/replacement copy and formats B/KB/MB sizes. Dragging a file updates the native input as well as the model; disabled fields reject drops, and resetting the model clears the native selection. Callers supply contextual hints and validation, such as QA formats or image limits. The sidecar specimen represents this reusable control; its Vue behavior remains owned by the source component.

### Page Headers / Tabs

`UiPageHeader` supplies the page title, description and action region. Desktop spacing uses a 24px gap and 28px bottom margin. Mobile wraps with an 18px gap and 24px bottom margin; action buttons can share the row width. Title and description use the canonical roles above.

`UiTabs` supplies a shared 44px-high row, 13px/500 labels, 16px/1.75 icons and a two-pixel selected green underline. The row gap is 24px with 24px inline padding, becoming 20px and 18px on mobile. Counts use metadata size in small rectangular labels; selected counts use soft green/green while inactive counts use subtle-surface/muted. Tabs use roving tabindex with Left/Right wrap, Home and End navigation, moving selection and focus together and linking each tab to its panel.

### Notices / Empty, Loading and Error States

`UiNotice` uses 13px regular text at line-height 1.8 with 14px 16px padding, reducing to 12px padding on mobile. Info uses subtle surface/ink; success uses soft green/green; error uses the destructive pair; warning uses the amber pair. Error notices announce with `role="alert"`; other tones use `role="status"`. Dismiss actions use the shared compact ghost icon button.

`UiEmptyState` shares the same icon/title/body/action composition for blank, loading and error conditions. Normal state uses 300px minimum height and 48px 24px padding; compact uses 170px and 32px 20px. Mobile regular padding becomes 40px 20px. Titles use the section role and bodies use 13px regular muted text, line-height 1.8, capped at 46ch. Loading uses status semantics and a spinner; errors use alert semantics and a destructive icon. All states retain the shared action controls.

### Navigation / Status / Containers

App navigation uses the deep rail, icon-plus-label links, the control radius and a pale-leaf active row with dark text. Desktop links use body size; mobile uses metadata size and a 42px minimum height. Collection choices use their existing soft-green selection and wrapping content labels; categories and view selectors use shared compact ghost buttons with pressed state.

Index and generation status labels use compact rectangular shapes. Neutral status uses a subtle fill, indexed/completed uses soft green and green text, and warning uses amber. Library, preview, catalog and editor surfaces share paper, fine borders and panel corners. Editor asides use subtle surface and a rule; catalog entries combine a CSS/SVG sheet cue with category, wrapping title, description and shared actions. Grid and list presentations preserve that hierarchy.

### Resource Preview / Generated Text

The document template library uses the same workbench palette and shared controls. Its source tabs distinguish built-in starter definitions from workspace copies, and category choices reflect actual template records. Starter thumbnails show real section names. The inline structure preview pairs working paper with an action aside, stacks below 800px, and explicitly distinguishes structure from Word pagination. The upload page offers a direct library entry and category/description fields. Template behavior and provenance are recorded in `docs/TEMPLATE_LIBRARY.md` and the template surface contract; no global tokens or raster assets were added.

The upload preparation surface now pairs the import form with existing-template choices, preceded by the actual preparation/fill/export sequence. It reveals the content editor and an independently sized, sticky export summary only after a template is prepared; the initial surface avoids an empty variable editor or stretched result column. Four library records lead to catalog search for that exact template. Below 800px the preparation and content columns stack; below 640px metadata fields stack. `create.css` arranges this surface while canonical controls and all shared visual tokens retain their owners.

Resource rows combine a wrapping source name, metadata and text readiness label. Hover and active-source fills differ subtly; title hover underlines. Retrieval exposes source actions and excerpts, with highlight fill behind ink text. Opening a source focuses its shared close action; closing restores the trigger or active library tab. Escape also closes it. The preview is an adjacent reading region rather than a modal focus trap.

Source and generated prose use the reading role, preserve whitespace and wrap long content. Reading segments are explicitly labeled as browsing aids. The preview enters over 220ms with an 8px horizontal move and slight brightness change. The shared reduced-motion query removes animations and transitions. Generation history and downloads retain the same semantic palette and shared primitives.

## Do's and Don'ts

### Do:

- **Do** use the shared UI components and canonical ui.css primitives across knowledge and document flows.
- **Do** keep action text at 13px/500 and action icons at 16px with 1.75 stroke width in both control sizes.
- **Do** preserve intentional heading, title, section and reading roles while inheriting the same working family.
- **Do** use semantic color tokens, shared notice tones and shared empty/loading/error patterns.
- **Do** preserve visible keyboard focus, roving tab navigation, reduced-motion support and source preview focus restoration.

### Don't:

- **Don’t** redefine a shared button’s height, font, color, radius or icon geometry in page CSS.
- **Don’t** shrink compact action labels; compact changes geometry while preserving 13px/500 text.
- **Don’t** restore emoji iconography, blue glow shadows or decorative gradients from the replaced interface.
- **Don’t** add shadows to every container; use border and surface tone for resting structure.
- **Don’t** present reading segments, index readiness, counts or answers as decoration; their labels and states must follow actual data.

Not canonized: the knowledge task menu, grouped form layout and graph/result composition are surface-specific behavior, documented in the knowledge surface contract and capability record rather than added as global design rules. No page-local control exceptions remain in this recorded implementation. Earlier compact-size, font and color discrepancies have been removed; the deliberate content hierarchy remains. No shipped raster assets belong to this system.
