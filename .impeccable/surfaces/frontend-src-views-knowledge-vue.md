---
version: 1
slug: "frontend-src-views-knowledge-vue"
primary_target: "frontend/src/views/Knowledge.vue"
related_targets: ["frontend/src/App.vue","frontend/src/styles/knowledge.css","frontend/src/styles/workbench.css"]
---

# Knowledge workbench

Mode: Operate. Audience: Chinese-speaking self-hosted workspace users organizing source material before document writing. Primary task: import, inspect, retrieve and reuse a source. User requested a substantial feature upgrade and redesign after finding the initial knowledge page too simple and ugly.

## Current direction contract — 2026-10-20

THESIS: Make source inspection the center of the knowledge workflow, with the selected document and its retrieval evidence one action apart.

OWN-WORLD: The user-selected “Vue 模板市场：深蓝顶部导航、白色内容卡片、蓝色按钮”. Deep navy horizontal top navigation, white working cards, cool slate canvas/text and blue actions/selection. One system sans family including the compact bold wordmark; compact rules and Lucide line icons. Current normative tokens and responsive geometry live in DESIGN.md.

STORY: Choose a collection, import files or paste text, check the extracted original, retrieve relevant sources, then carry the collection into writing. Counts and index states reflect actual storage.

FIRST VIEWPORT: A full-width navy top header with horizontal icon navigation, white workspace bar and content capped at 1488px. The 190px collection list and flexible document table retain page-level import/create actions. Opening a source introduces a 380px right preview from 1360px; narrower desktop/tablet uses the bounded floating preview. At 800px and below top navigation wraps to a second horizontal row. Mobile switches collections to horizontal choices and opens a full-width source view.

FORM: Code-led restoration of the original Vue application at commit 5c2799899abcfba6d1aecd0b0a340ecca5b04e71, anchored by actual original market/create captures. This explicitly replaces the former reading/field-guide workbench (candidate 4, seed 04518e4f), whose initial preference did not constitute acceptance of the later rejected visual result. No approved comp or pixel-exact reproduction claim exists. Final human taste acceptance remains the user’s.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Quality bar

Controls retain conventional behavior and visible labels; source names and text remain legible in Chinese. Management, retrieval and preview must work at 1440px and 390px with no page overflow. Empty, loading, errors, missing models, imports and removal all have explicit states. No invented statistics, OCR capability, vector chunks or model answers. Reading segments are labeled as a browsing aid. Search source navigation is the signature interaction. No knowledge-specific raster assets. The twelve authentic starter DOCX covers in the template workflows retain their source/hash provenance.

## Historical refinements — superseded visual identity

The following sections preserve earlier functional decisions and their sequence. Warm-green, serif-wordmark and app-rail guidance below is historical and must not override the current direction contract or DESIGN.md. The current pass retains all seven knowledge tabs and 28 operation entries; provider gates and real-data requirements remain binding. Final review inspected the 24-state matrix at 1440px/1024px/390px and found no material visual fixes. Bounded test/deployment results are in docs/VALIDATION.md.

### Reference-driven refinement

The user requested further UI optimization using VoltAgent/awesome-design-md. Preserve the confirmed Operate reading-workbench world. Adapt control consistency and surface discipline from the Linear analysis, neutral text and template presentation from Notion, and reading hierarchy from Mintlify. These are marketing-site analyses translated to app tasks, not literal application templates. References and source revision are recorded in docs/UI_REFERENCES.md.

Source preview now uses 15px ink text and a 380px desktop pane (420px at wide sizes); three-column composition starts at 1360px, with a floating preview below that and a full-width mobile view. Shared controls, spacing and paper/green styling extend to writing and all template workflows. Verify knowledge and document paths at 1440px, 1024px and 390px, including real upload, variable fill, authenticated download, keyboard source entry/return and no page overflow. No paid model calls or shipped raster assets.

## Consistency correction after user feedback

The user rejected the previous claim of UI unity and specified buttons, typography and colors as the visible problem. This correction preserves the reading-workbench direction and replaces separate visual implementations with UiButton, UiPageHeader, UiNotice, UiEmptyState and UiTabs plus canonical ui.css. Standard controls use 40px/32px heights at desktop, 44px/40px on mobile, 13px/500 button text, 6px control radius and 16px/1.75 action icons. Fields use 14px/400 text (16px mobile); regular headings, body and metadata use the shared type tokens. Ink, muted, action, focus and semantic feedback colors have one owner. Page styles arrange controls without redefining their visual properties. Review the actual computed styles across all five routes and the three viewport widths, as well as the capture matrix and the user's feedback; a clean detector or functional smoke pass is insufficient evidence of visual unity.

## Knowledge capability expansion — 2026-10-17

Extend the existing Operate surface and keep the shared control system. The user requires backend knowledge capabilities to be represented in the page. Preserve the collection rail, document table and source preview; add task tabs for import/parse, stored chunks/analysis, graph, settings and advanced retrieval. A compact task menu leads to one form and its structured results. Dependency failures remain visible and actionable; stored chunks, model output and graph data must never be invented. Desktop uses a task menu beside the form; mobile wraps the task navigation above it. Batch IDs remain accessible after switching tasks. Review desktop and mobile for discovery, form semantics, explicit partial failures and the same button/type/color roles. No new brand, tokens or raster assets are introduced.

## Full task polish — 2026-10-17

Preserve the established palette, type ramp and control geometry across the knowledge and document workspace. Give all seven knowledge tabs and 28 task entries consistent line icons. On desktop, pair a 200px task menu with one grouped form; on mobile, show a compact native-button task disclosure and return focus to the selected task heading. Use the shared Chinese file picker for upload and image queries, retaining native file, required and keyboard behavior. Keep prose and result states prominent, with opaque identifiers and debug metadata disclosed separately; show actual graph edges and labels at readable contrast. Same 1440px/390px evidence matrix covers management, empty upload, QA entry, real chunks, unavailable graph, metadata, advanced results and explicitly synthetic graph data. Existing template and writing controls remain the canonical consistency comparison.
