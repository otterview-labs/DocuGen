---
version: 1
slug: "frontend-src-views-knowledge-vue"
primary_target: "frontend/src/views/Knowledge.vue"
related_targets: ["frontend/src/App.vue","frontend/src/styles/knowledge.css","frontend/src/styles/workbench.css"]
---

# Knowledge workbench

Mode: Operate. Audience: Chinese-speaking self-hosted workspace users organizing source material before document writing. Primary task: import, inspect, retrieve and reuse a source. User requested a substantial feature upgrade and redesign after finding the initial knowledge page too simple and ugly.

## Direction contract

THESIS: Make source inspection the center of the knowledge workflow, with the selected document and its retrieval evidence one action apart.

OWN-WORLD: Deep green navigation, warm white working paper, olive secondary information, compact rules and Lucide line icons. System sans for Chinese working text; a small Georgia wordmark. Brand expression stays in palette, type and density.

STORY: Choose a collection, import files or paste text, check the extracted original, retrieve relevant sources, then carry the collection into writing. Counts and index states reflect actual storage.

FIRST VIEWPORT: A 208px app rail, 190px collection list, flexible document table and page-level import/create actions. Opening a source introduces a 380px right preview at desktop widths. Mobile switches to collection chips and a full-width source view.

FORM: Grounded candidate 4, reading/field-guide workbench, direction seed 04518e4f. Code-led. The user confirmed this direction via the optional preference question. No approved comp or decision raster exists. Durable contract recorded during finish; it was not persisted before implementation.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Quality bar

Controls retain conventional behavior and visible labels; source names and text remain legible in Chinese. Management, retrieval and preview must work at 1440px and 390px with no page overflow. Empty, loading, errors, missing models, imports and removal all have explicit states. No invented statistics, OCR capability, vector chunks or model answers. Reading segments are labeled as a browsing aid. Search source navigation is the signature interaction. No shipped raster assets.

## Reference-driven refinement

The user requested further UI optimization using VoltAgent/awesome-design-md. Preserve the confirmed Operate reading-workbench world. Adapt control consistency and surface discipline from the Linear analysis, neutral text and template presentation from Notion, and reading hierarchy from Mintlify. These are marketing-site analyses translated to app tasks, not literal application templates. References and source revision are recorded in docs/UI_REFERENCES.md.

Source preview now uses 15px ink text and a 380px desktop pane (420px at wide sizes); three-column composition starts at 1360px, with a floating preview below that and a full-width mobile view. Shared controls, spacing and paper/green styling extend to writing and all template workflows. Verify knowledge and document paths at 1440px, 1024px and 390px, including real upload, variable fill, authenticated download, keyboard source entry/return and no page overflow. No paid model calls or shipped raster assets.
