---
name: DocuGen
description: 'The original Vue template-market visual family: navy top navigation, white cards and blue actions'
colors:
  accent: '#2563eb'
  accent-hover: '#1d4ed8'
  ink: '#0f172a'
  muted: '#64748b'
  paper: '#ffffff'
  ground: '#f8fafc'
  line: '#e2e8f0'
  sidebar: '#0f172a'
  sidebar-text: '#cbd5e1'
  nav-selected: '#1c3056'
  nav-selected-text: '#93c5fd'
  nav-hover: '#1e293b'
  header-muted: '#94a3b8'
  action-text: '#ffffff'
  danger: '#9d3a33'
  danger-soft: '#fcf0ec'
  focus: '#93c5fd'
  accent-soft: '#eff6ff'
  surface-subtle: '#f8fafc'
  amber: '#886222'
  amber-soft: '#f9f1df'
  line-strong: '#cbd5e1'
  hover: '#f1f5f9'
  highlight: '#dbeafe'
  brand-symbol: '#ffffff'
typography:
  wordmark:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 20px
    fontWeight: 800
    lineHeight: 1.2
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
  navigation:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
    fontSize: 14px
    fontWeight: 600
rounded:
  tag: 4px
  control: 6px
  identity: 8px
  panel: 14px
  navigation: 8px
  brand: 10px
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
    textColor: '{colors.nav-selected-text}'
    rounded: '{rounded.navigation}'
    padding: 10px 16px
    typography: '{typography.navigation}'
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

# Design System: DocuGen

## Overview

**Creative North Star: "The Vue Template Market"**

DocuGen restores the visual family the user explicitly selected on 2026-10-20: “Vue 模板市场：深蓝顶部导航、白色内容卡片、蓝色按钮”. A deep navy top band anchors horizontal icon navigation; white working cards sit on a cool light-gray canvas. Clear blue marks actions, selection and readiness. The wordmark and Chinese interface use the same platform sans family.

This current authority replaces the earlier warm-paper, green-sidebar reading-workbench identity. The reference is the actual original DocuGen Vue application at commit `5c2799899abcfba6d1aecd0b0a340ecca5b04e71`, captured in `artifacts/legacy-ui-comparison/original-market.png` and `original-create.png`. This is a code-led adaptation of that visual family to expanded knowledge, writing and template workflows; it makes no pixel-exact reproduction claim. Shared controls, content hierarchy, real Word covers and functional behavior continue to use their existing source owners. Final human taste acceptance remains with the user.

**Key Characteristics:**

- Deep navy horizontal navigation at every viewport width.
- Cool gray canvas, white cards, fine slate borders and clear blue actions.
- One platform sans family with a compact bold wordmark and consistent semantic text roles.
- Shared controls, keyboard tabs, source inspection and native file selection across knowledge and document flows.

## Colors

Navy navigation, cool neutrals and one blue action family establish the workspace. The frontmatter is normative. Shell palette tokens live in `frontend/src/styles/workbench.css`; `frontend/src/styles/ui.css` owns control, focus and highlight tokens. The source keeps the legacy custom-property names `sidebar` and `sidebar-text`, but they now style the top header. Navigation-only values are extracted from its actual rules. Sidecar tonal ramps are synthesized display aids rather than additional runtime colors.

### Primary

- **Action Blue** (`accent`, `accent-hover`): primary actions, readiness, selected tabs and the caret; hover deepens the fill and border.
- **Soft Blue** (`accent-soft`): selected categories, completed/indexed states and upload feedback.
- **Navigation Selection** (`nav-selected`, `nav-selected-text`): blue-toned selected destination against the navy header.

### Neutral

- **Slate Ink** (`ink`) and **Muted Slate** (`muted`): reading/headings and supporting metadata respectively.
- **White Card** (`paper`), **Cool Canvas** (`ground`) and **Subtle Surface** (`surface-subtle`): working panels, surrounding canvas and supporting asides.
- **Fine Rule** (`line`), **Control Rule** (`line-strong`) and **Control Hover** (`hover`): panel divisions, field/control borders and quiet secondary hover fills.
- **Navy Header** (`sidebar`), **Navigation Text** (`sidebar-text`), **Navigation Hover** (`nav-hover`) and **Header Metadata** (`header-muted`): top navigation and its contextual copy.
- **Action White** (`action-text`), **Brand Mark White** (`brand-symbol`), **Focus Blue** (`focus`) and **Source Highlight** (`highlight`): action contrast, identity icon, keyboard outline and matching-source emphasis.

Destructive actions retain `danger` and `danger-soft`; warnings, interrupted jobs and missing generation configuration retain `amber` and `amber-soft`. Their existing semantic values are preserved.

**The Blue Action Rule.** Use blue for actions, readiness and selection. Keep sustained reading in slate ink and working cards white beneath the navy top navigation.

## Typography

**Wordmark Font:** the same platform sans stack as the working interface.
**Working Font:** `--font-family-working`, defined in `ui.css` and recorded in the frontmatter: the platform sans stack including PingFang SC and Microsoft YaHei. Root text, all native controls and content links inherit it. No web font or raster wordmark is shipped.

The hierarchy distinguishes reading and navigation tasks without changing the action label role between pages or sizes.

- **Wordmark:** 20px/800 on desktop, 18px/800 at 640px and below; line-height 1.2 and letter-spacing −0.025em. Header navigation uses 14px/600, reducing to 12px on mobile.
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

The shell has a full-width navy top header and horizontal navigation at every size. Its inner container is capped at 1488px with 16px 32px padding, an 80px minimum height and 36px group gap. The brand icon is a 44px blue square; the workspace bar below is at least 48px high. Main content is capped at 1488px and uses 36px 32px 48px padding. Document workspaces retain a 1280px cap. The shared four-pixel spacing foundation runs through 32px; intermediate observed values serve local information groups.

At 1100px and below, the header gap becomes 24px, navigation horizontal padding becomes 12px and identity copy hides. At 800px and below, navigation wraps to its own full-width second row, with evenly shared links; header padding becomes 16px 24px and content uses 28px 24px 40px. At 640px and below, header padding becomes 14px 16px 10px, the brand icon becomes 36px, its subtitle hides, navigation has 4px gaps and 42px minimum-height links, the workspace bar is at least 44px high, and content uses 24px 16px 32px. The header remains in normal flow; there is no app sidebar or tablet icon rail.

The knowledge reference surface uses a collection rail (190px), flexible library panel and a 23px gap. With preview open from 1360px, it uses 176px / flexible / 380px columns with a 17px gap. From 1600px, this becomes 190px / flexible / 420px with a 23px gap. The source panel is sticky, 24px from the top, with a maximum height of `calc(100dvh - 112px)` and an independently scrolling prose region.

Between 641px and 1359px, the collection rail is 160px and the preview floats 20px from the right and bottom and 100px from the top. Its final width is `min(440px, calc(100vw - 110px))`; this overrides the earlier fixed-width declaration.

Document editing uses a flexible main region with a 300px supporting aside, divided by a rule inside one paper panel. At 1100px and below, the aside becomes 260px and variable fields move from two columns to one. At 800px and below, the aside stacks below the main region. The catalog changes from three equal columns to two at 1100px and one at 640px; its alternative list view keeps document context and actions together.

At 640px and below, collections become horizontal choices. Source preview replaces the list and collection region with full-width reading content in document flow. Optional table columns disappear, filters and actions wrap, and file-type tiles are hidden to protect title space. Document forms, variable entry and submit controls stack; catalog rows become one-column entries.

## Elevation & Depth

Tonal separation and one-pixel borders provide ordinary structure. Library, document editor, catalog and inline source panels have no shadow. The connection popover uses `0 15px 40px #0f172a24`; the intermediate-width floating preview uses `-12px 15px 40px #0f172a1a`. Shared tabs use a two-pixel selected underline; it is an indicator, not container elevation.

**The Flat Workbench Rule.** Keep ordinary library, editor, catalog and inline preview surfaces flat with fine borders. Reserve soft shadows for the connection popover and the intermediate-width floating preview.

## Shapes

The form language is restrained and rectangular. Shared controls use `control-radius` (with the matching shell `radius-control` alias); shared panels and document editors use `radius-panel`. Compact status labels and document-sheet motifs use the tag radius. Navigation links use their own 8px radius; the blue brand square uses 10px on desktop and 8px on mobile. Panels use 14px corners and controls retain 6px corners. One-pixel rules divide rows, tabs, editor sections and catalog entries. Horizontal collection choices remain gently rounded rectangles rather than pills.

Lucide outline icons replace the old template emoji and support all working flows. Action and tab icons use exactly 16px with 1.75 stroke width. Empty-state icons use 32px/1.6 and upload icons use 26px/1.6, preserving their different roles; the wordmark remains bold sans. Header navigation icons use 19px/1.7 on desktop and 15px on mobile; the brand document icon is 24px/1.7. Workspace template-sheet motifs remain CSS-and-SVG document cues; built-in starter covers use the bounded authentic-document thumbnail exception described in Components.

## Components

### Shared Ownership

Use `UiButton`, `UiPageHeader`, `UiNotice`, `UiEmptyState`, `UiTabs` and `UiFilePicker` from `frontend/src/components/ui`. Their visual rules live in `frontend/src/styles/ui.css`. Page styles arrange shared controls without redefining their typography, colors, shape or geometry. App navigation, source titles, document prose and collection choices retain their intentional content roles. Shared form rows use a 12px gap; the retrieval search group that contains an action uses 8px padding and gap.

### Buttons

`UiButton` renders a native button, RouterLink or anchor with one visual contract. Standard controls are 40px high with 0 14px padding; compact controls are 32px with 0 10px padding. At mobile widths, their heights become 44px and 40px respectively. Icon-only controls are square at the selected size. Every action label stays 13px/500, every action icon is 16px with 1.75 stroke width, and every button uses the 6px control radius.

Secondary buttons use paper, ink and the strong control border. Primary buttons use blue and action-white, with both fill and border deepening on hover. Ghost buttons use transparent fill/border and muted text, gaining ink text and the shared hover fill. Text buttons use blue with transparent fill/border, zero inline padding and compact height; choosing compact size applies its 10px inline padding. Their hover underlines at a 4px offset. Danger buttons use destructive fill, text and border. Pressed controls use soft blue and blue text. Disabled controls use 0.5 opacity and a not-allowed cursor. State transitions last 150ms; keyboard focus uses a 3px ring with a 3px offset.

Native `UiButton` defaults to `type="button"`; real form submissions declare `type="submit"` explicitly. Preserve that behavior when adding forms, including connection settings, knowledge import/search and writing.

### Inputs / Search / Upload

Shared fields use paper, ink, a strong one-pixel border, 6px corners and 9px 11px padding. Inputs and selects have the standard control height; textareas have that minimum height and resize vertically. Field text is 14px/400, 16px on mobile; labels are 13px/600. Focus changes the border to blue and uses a 3px ring with a 2px offset. Placeholder text uses muted neutral at regular weight.

Grouped search uses the same paper/border geometry, 16px/1.75 icon and an inherited working-family input. Focus surrounds the whole group. Search with an embedded action adds 8px padding and gap. Full upload regions share a dashed strong border, subtle surface, 156px minimum height and centered copy. Hover or dragging uses soft blue and a blue border; whole-region focus stays visible.

### File Picker

`UiFilePicker` owns compact single-file selection in `frontend/src/components/ui/UiFilePicker.vue`; its visual states belong to `ui.css`. It uses the existing subtle surface, strong dashed border and control radius, with a 104px minimum height, 20px padding and 16px icon-to-copy gap. At 640px and below, these become 100px, 16px and 12px. The leading upload/file icon is 24px with 1.75 stroke width; a selected file adds an 18px check. File names use body-size medium ink text and wrap; hints and formatted sizes use regular metadata text. Hover or drag uses soft blue with a blue border and blue hint text; selection changes the border to solid. Focus within uses the shared 3px ring and 3px offset; disabled selection uses 0.52 opacity and a not-allowed pointer.

The transparent native file input covers the selection region and retains its accessible label, `accept`, `required`, disabled and keyboard behavior. The component exposes a single File or null through `v-model`, shows Chinese selection/replacement copy and formats B/KB/MB sizes. Dragging a file updates the native input as well as the model; disabled fields reject drops, and resetting the model clears the native selection. Callers supply contextual hints and validation, such as QA formats or image limits. The sidecar specimen represents this reusable control; its Vue behavior remains owned by the source component.

### Page Headers / Tabs

`UiPageHeader` supplies the page title, description and action region. Desktop spacing uses a 24px gap and 28px bottom margin. Mobile wraps with an 18px gap and 24px bottom margin; action buttons can share the row width. Title and description use the canonical roles above.

`UiTabs` supplies a shared 44px-high row, 13px/500 labels, 16px/1.75 icons and a two-pixel selected blue underline. The row gap is 24px with 24px inline padding, becoming 20px and 18px on mobile. Counts use metadata size in small rectangular labels; selected counts use soft blue/blue while inactive counts use subtle-surface/muted. Tabs use roving tabindex with Left/Right wrap, Home and End navigation, moving selection and focus together and linking each tab to its panel.

### Notices / Empty, Loading and Error States

`UiNotice` uses 13px regular text at line-height 1.8 with 14px 16px padding, reducing to 12px padding on mobile. Info uses subtle surface/ink; success uses soft blue/blue; error uses the destructive pair; warning uses the amber pair. Error notices announce with `role="alert"`; other tones use `role="status"`. Dismiss actions use the shared compact ghost icon button.

`UiEmptyState` shares the same icon/title/body/action composition for blank, loading and error conditions. Normal state uses 300px minimum height and 48px 24px padding; compact uses 170px and 32px 20px. Mobile regular padding becomes 40px 20px. Titles use the section role and bodies use 13px regular muted text, line-height 1.8, capped at 46ch. Loading uses status semantics and a spinner; errors use alert semantics and a destructive icon. All states retain the shared action controls.

### Navigation / Status / Containers

App navigation uses the navy top header, horizontal icon-plus-label links, 8px corners and a blue-toned selected link with light blue text. Desktop links use 14px/600 with 10px 16px padding; hover uses the slate header-hover fill and white text. Mobile retains the horizontal second row, uses 12px/600 and a 42px minimum height with 9px 4px padding. Collection choices use their existing soft-blue selection and wrapping content labels; categories and view selectors use shared compact ghost buttons with pressed state.

Index and generation status labels use compact rectangular shapes. Neutral status uses a subtle fill, indexed/completed uses soft blue and blue text, and warning uses amber. Library, preview, catalog and editor surfaces share paper, fine borders and panel corners. Editor asides use subtle surface and a rule; catalog entries combine a document cover with category, wrapping title, description and shared actions. Built-in covers use authentic document thumbnails; workspace entries retain the CSS/SVG sheet cue. Grid and list presentations preserve that hierarchy, with covers omitted from the narrower list layout.

### Resource Preview / Generated Text

The document template library uses the same workbench palette and shared controls. Its source tabs distinguish built-in starter definitions from workspace copies, and category choices reflect actual template records. Built-in covers render the first page of the actual starter DOCX and retain embedded source metadata plus a companion provenance manifest. This bounded raster exception supplies useful document context without introducing a new visual theme. The inline structure preview remains a separate reading view: it pairs working paper with an action aside, stacks below 800px, and explicitly distinguishes structure from Word pagination. Template behavior, thumbnail provenance and rendering limits are recorded in `docs/TEMPLATE_LIBRARY.md` and the template surface contract; global visual tokens are unchanged.

The upload preparation surface begins with a gallery of four actual starter covers, followed by workspace selection and a compact Word import panel. A cover link opens the catalog filtered to that starter; its adjacent shared action installs or reuses the starter and opens the existing editor. The page header's “导入 Word” shortcut scrolls to import and focuses native file selection. The gallery has four columns above 800px and two below; import columns stack at 800px and metadata fields at 640px. The content editor and independently sized, sticky export summary appear only after a template is selected or uploaded; these columns stack below 800px. `create.css` arranges this surface while canonical controls and all shared visual tokens retain their owners. This composition is surface-specific, rather than a new rule for other routes.

`TemplateCover` displays a cropped first-page view with the original document proportions inside the existing ground, border and control-corner vocabulary. It is an orientation thumbnail, not a readable replacement for downloading the Word file. Images load lazily; failure shows the real template name, up to three actual section titles and an explicit unavailable-image message while the structure and use actions remain available. Custom uploads do not acquire generated covers through this change. Font substitution and the rendering application can alter line breaks and pagination; a filled or edited document can differ from this starter snapshot.

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
- **Don’t** reintroduce the user-rejected warm-green sidebar or serif wordmark as the current app identity.
- **Don’t** add shadows to every container; use border and surface tone for resting structure.
- **Don’t** present reading segments, index readiness, counts or answers as decoration; their labels and states must follow actual data.

Not canonized: the knowledge task menu, grouped form layout and graph/result composition are surface-specific behavior, documented in the knowledge surface contract and capability record rather than added as global design rules. The current shell and shared-control record was extracted after the approved navy/white/blue replacement; historical surface decisions do not override it. Shipped raster assets are limited here to the twelve authentic starter DOCX first-page thumbnails in `frontend/public/template-previews`, with embedded provenance and a source/hash manifest. This exception does not authorize decorative or AI-generated imagery, customer-template captures or a raster wordmark.
