# Document template library

## Current direction — template-to-document workflow, 2026-10-20

Mode: Operate, code-led extension of the existing Vue 3 application. The accepted world is fixed by `DESIGN.md`: navy horizontal navigation, sans wordmark, white cards, cool gray ground and blue shared controls. Original-source references are recorded in `docs/UI_REFERENCES.md`; this is not a pixel-exact reproduction. All twelve original starter DOCX thumbnails and embedded/source-hash provenance remain intact; this extension adds no raster or shared token/component changes. Final human taste acceptance remains the user’s.

## Direction contract

THESIS: Make the main task explicit: catalog → dedicated content editor → Word export. The earlier four-cover gallery and inline editor on `/create` are superseded; import has its own form, and selection moves directly into filling.

OWN-WORLD: Inherit navy/white/blue, the platform sans family, fine borders and existing panel/control corners. `ui.css` continues to own action text, colors, geometry and focus. Route CSS changes composition only.

STORY: Inspect an authentic cover and optional variables/sections, use its workspace copy, fill grouped information and content, check live field values, generate and download. Upload and saved-template selection converge on the same editor. Manual filling/export remain model-free; reference, AI, retrieval and source records remain available.

FIRST VIEWPORT: The catalog leads with real cover previews and compact primary use actions. The upload route shows its form beside existing-template choices. The editor presents fields beside a sticky export/content-review panel; under 800px these stack, with a fixed shortcut focusing the real generate button. Content review explicitly checks values rather than rendering Word layout.

FORM: User-authorized, precisely scoped extension; no new concept seed or comp round. Per-template session-tab drafts restore declared fields and assistance context without mixing templates; loaded long/multiline/non-ISO values receive safe text controls that remain stable while typing. Storage failure is nonblocking, variable refresh preserves surviving values, and value/source edits invalidate stale download actions.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Current evidence comprises 18 captures of catalog, preview, import, studio, filled and restored states at 1440px, 1024px and 390px under `.impeccable/review/document-studio/`, plus functional and shared-control checks. Review and rollout status belong to the current extension entry in `docs/VALIDATION.md`; the earlier visual restoration’s ship verdict does not transfer to this workflow. Advanced knowledge reorganization and free-writing improvements remain separate work.

## Historical functional and composition decisions

The following records describe superseded compositions, including the four-cover `/create` gallery and editor revealed on that route. Their functional constraints and provenance remain relevant; their warm-green visual commitments and upload layout are superseded by the current direction above.

Mode: Operate. Preserve the accepted reading-workbench identity, shared controls, typography, warm paper and deep green navigation. User feedback: the merged `/create` surface made the original template-led workflow hard to find, and the available template content was too sparse.

Provide actual reusable DOCX templates, distinguish built-in definitions from saved workspace copies, and let users understand the content before committing to a template. The catalog retains categories, search, grid/list views and pagination. Built-in entries now show a thumbnail rendered from the actual starter DOCX first page; workspace entries retain the document icon. The separate inline structure preview pairs a paper reading region with metadata and actions on desktop, stacking on mobile. That reading view remains explicitly structural, not a rendered Word screenshot or pagination guarantee. Original download and manual filling work without a model. Upload preserves custom category and description.

Focus enters the inline preview and returns to its trigger on close; Escape closes it. Tabs use the shared keyboard behavior. Use existing tokens and components; no global design-token changes. The only shipping raster exception is twelve original starter first-page PNGs with embedded provenance and the source/hash manifest in `frontend/public/template-previews`. Do not derive assets from customer files or use AI image generation. Verify actual DOCX output, catalog-to-editor navigation, downloads, duplicate/colliding names, upload metadata, shared-control styles and layouts at 1440px, 1024px and 390px. Previous deployment templates are not claimed as migrated; the twelve starters are original content definitions.

## Earlier upload composition refinement

The user rejected the previous `/create` presentation as visually worse. Preserve the existing reading-workbench palette and canonical controls, but replace the oversized introductory banner and one long upload/variable/result container. A real three-stage guide precedes two adjacent preparation regions: the Word upload form and existing-template choices. Four actual starter records link to a filtered catalog using the template name; counts and labels come from the library API. Errors retain their message and retry action without disabling file import.

Initially no template is implicitly selected. Content fields and the compact export summary appear after upload or explicit selection, reducing irrelevant empty/disabled regions. Template switching clears the previous download and retrieval sources; explicit re-extraction continues to preserve confirmed values. On desktop, preparation uses a 1.55:1 split and the variable region has a 300px sticky export summary; below 800px these stack, and below 640px fields stack as well. Use page-local `create.css` only for composition and content roles, with shared controls unchanged. Bounded desktop/tablet/mobile captures cover initial and selected-template states; the complete browser suite passed 35 tests, with the optional real-model invocation skipped. No shipping raster assets or palette changes.

## Document-first correction preceding the visual replacement

The user rejected the preceding `/create` attempts twice because the change was not visually apparent. The correction changes the first visible composition while preserving the reading-workbench world: four authentic starter covers lead the page, with a workspace-template selector and compact upload panel below. The featured records are 项目实施方案、项目验收报告、工作周报 and 会议纪要, selected by their real library identifiers. Names, category labels, variable counts and the full-library count come from the API.

Each featured cover links to `/templates?source=builtin&q=<name>` for the exact starter; the separate “使用模板” action installs or reuses its workspace copy and opens the existing editor directly. The top “导入 Word” shortcut scrolls to the upload heading and transfers focus to the native file input. A library retrieval error retains its real message and retry action while import remains available; starter-action errors remain explicit. No initial template is selected implicitly. Prepared fields, explicit variable refresh and export continue to use the existing workflows.

The gallery uses four columns above 800px and two at or below 800px, including mobile. Below it, the import panel uses two columns until 800px and stacks on narrower screens; metadata fields become one column at 640px. The prepared-content region retains a 300px export aside, 260px at or below 1100px, and stacks at 800px. Shared control appearance and all visual token values are preserved. The catalog reuses `TemplateCover`; list covers are compact on wide screens and hidden at or below 1100px.

Thumbnails are generated read-only from `/api/template-library` and its original DOCX download routes through `scripts/export_template_previews.py`, a document renderer and LibreOffice. PNG metadata records the source and `provenance.json` records definitions and downloaded DOCX SHA256 values. The utility never installs a template or writes workspace data. See `docs/TEMPLATE_LIBRARY.md` for dependencies and a portable regeneration command. Keep that provenance with the assets.

`TemplateCover` uses lazy image loading and a fixed-height crop of a proportionate first-page image. It shows real template/section text plus an explicit image-unavailable message on failure; structure and use actions remain usable. These thumbnails are snapshots of empty original starters, not a guarantee of readable body text at gallery scale, full-document coverage or Word pagination. Font availability, font substitution, render-engine differences and filled content can change layout. Uploaded customer files are outside this asset scope.

Earlier validation counts above apply to their historical refinement. The current replacement’s final screenshot review and bounded checks are recorded separately in `docs/VALIDATION.md`; they do not retrospectively establish user acceptance of any earlier presentation.
