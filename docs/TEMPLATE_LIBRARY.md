# Template library and DocuGen comparison

The template flow now includes twelve original starter templates, distinct from uploaded workspace files. Their content definitions and DOCX formatting are in `quill/template_library.py`; no customer or archived runtime documents are bundled.

The compared DocuGen snapshot is `BetaStreetOmnis/DocuGen@5c2799899abcfba6d1aecd0b0a340ecca5b04e71`. Its Vue catalog has category filters, search, grid/list presentation and a template API. The tracked `templates/` directory contains two Word files (`1212.docx`, `投标文件.docx`). The snapshot's `app.py` references a `template_store` module not present in that tree. This evidence does not establish how many uploaded templates existed in the previous running deployment. Those runtime files have not been migrated or replaced by the starter library.

## User flow

- `/templates` combines workspace files and the starter library, with separate source tabs. Workspace files come first in the combined view. Search includes template names, descriptions and variable names; category choices reflect the current source's actual records. Grid/list and pagination remain available.
- Starter entries show first-page thumbnails rendered from their actual DOCX files. “查看结构” opens a separate inline reading view using actual section names from the same definition that builds the Word file, explicitly distinguished from Word pagination. Keyboard focus moves into the structure preview and returns on close; Escape closes it.
- Original starter DOCX files download without model setup or installation. “使用模板” stores one editable workspace copy and opens the existing variable editor. Installation is idempotent, survives restarts, and chooses another name when a custom upload already owns the default name. Existing workspace metadata and files are preserved.
- `/create` offers an explicit library entry and accepts a category and description for custom uploads. Generated documents continue to use the uploaded DOCX's original styles. Starter copies use A4, a title, a metadata table, headings, a header and a PAGE field.
- `/create` begins with four real starter covers: 项目实施方案、项目验收报告、工作周报 and 会议纪要. Each cover opens `/templates?source=builtin&q=<name>` with the corresponding catalog filter; its “使用模板” action installs or reuses a workspace copy and goes directly to the editor. The gallery uses four columns above 800px and two below. Workspace-template selection follows, then a compact import form with category/description fields. The top “导入 Word” action scrolls to import and focuses native file selection.
- No template is automatically selected on arrival. Selecting or uploading a workspace template reveals the content editor and compact export summary on `/create`. Switching templates clears stale download/source state; explicit variable refresh preserves confirmed fields. Library failures retain their error and retry action while file import remains available.
- Manual filling and export require no model or API key in the local deployment. AI filling retains the existing model dependency.

## Templates

项目实施方案、技术方案、运维服务方案、项目验收报告、工作周报、会议纪要、项目进展报告、商务报价单、投标响应文件、个人简历、商务函件、需求说明书。

These are reusable content frameworks with a consistent base Word layout. They are not recreations of the previous deployment's templates or twelve unrelated visual themes. Download and edit the DOCX in Word to create another layout, then upload it as a workspace template.

## Authentic first-page thumbnails

The bounded raster asset exception consists of twelve PNGs in `frontend/public/template-previews`, one for each original starter, reused by the `/create` gallery and `/templates` catalog. `TemplateCover.vue` displays the first-page image at its original proportions inside a fixed-height, cropped cover region. Desktop catalog list view uses a compact cover; at or below 1100px list covers are hidden. These covers provide document orientation; download the DOCX for readable full content and editing. The existing inline structure view remains a separate HTML reading view.

The images originate only from the original definitions in `quill/template_library.py`, downloaded from the local library API and rendered with LibreOffice. No customer data, archived runtime templates or AI-generated imagery is used. Every PNG embeds source text in its `Source`, `Description` and `parameters` metadata; `provenance.json` records the template identifier/name, origin, full API definition and SHA256 of the exact downloaded DOCX. Preserve both embedded metadata and the manifest when updating assets. The DOCX hash identifies that downloaded artifact; regeneration can differ because DOCX packaging metadata, renderer versions and fonts can differ.

These are starter first-page snapshots, rather than pagination or fidelity guarantees. Fonts must be available to the renderer, including Chinese glyph coverage; missing fonts can produce substitution, unreadable glyphs or different line breaks. LibreOffice and Microsoft Word may paginate differently. The gallery crop does not expose the whole page, later pages are not included, and filled or edited documents can flow differently. Custom workspace uploads do not receive captured thumbnails through this utility. If a cover fails to load, the shared component shows the actual template name, up to three real section titles and an explicit unavailable-image message; structure and use actions remain available.

## Regenerating thumbnails

Run from the repository root against a local DocuGen API serving the starter library. The utility issues GET requests to `/api/template-library` and `/api/template-library/<id>/download`, writes temporary DOCX/render outputs and replaces the PNGs and manifest in the chosen output directory. It does not install templates, change workspace records or call a model. Its current HTTP client sends no workspace access key; use a local loopback deployment with the optional key empty.

Prerequisites: Python with Pillow, a compatible `render_docx.py` (for example the Codex documents skill renderer), LibreOffice/`soffice`, Poppler (`pdfinfo` and `pdftoppm`) and the renderer's Python dependencies, including `pdf2image`. Ensure the runtime can locate the required executables and fonts. Supply the renderer's path explicitly; it is external developer tooling rather than a bundled repository dependency.

```sh
python scripts/export_template_previews.py \
  --base-url http://127.0.0.1:8080 \
  --renderer /path/to/documents/render_docx.py \
  --output frontend/public/template-previews
```

The renderer must accept a DOCX path with `--output_dir`, `--width 420` and `--height 594`, and produce `page-1.png`. The utility renders the document then retains the first page, converting it to RGB and embedding origin metadata through Pillow. An optional `--embed-tool /path/to/impeccable-launcher` additionally invokes that tool's `embed-prompt` command; the three source metadata fields and manifest are written even without it. After regeneration, inspect all twelve images for legibility and source agreement before accepting updated assets. This regeneration is developer work, not a runtime requirement for viewing the shipped gallery.

## Validation

Backend coverage downloads, installs, fills and reads all twelve actual DOCX files. It checks values, multiline content, placeholder removal, title/table/heading styles, page size, headers and PAGE fields, plus authorization, invalid identifiers, repeated installation and same-name preservation. Browser coverage exercises the complete starter flow, original download, generation, source filters, custom upload metadata, keyboard focus and 1440/1024/390px layouts. Existing cross-route control checks continue to apply.

Validation result: 55 workspace tests and Ruff passed; the full browser suite passed 33 tests, with the explicitly opt-in real-model test skipped in this run. The downloaded project-plan DOCX was rendered and visually inspected: one readable page, black title without the inherited blue rule, correctly proportioned information table, six sections, header and page number. Browser captures are local test artifacts, not shipped raster assets. Knowledge-engine source was unchanged.

Subsequent upload presentation refinement: frontend build and 35 browser tests passed, with one optional real-model test skipped. New checks cover deliberate initial selection, the exact-template shortcut and an unavailable-library retry while file input remains enabled. Desktop, tablet and mobile captures at 1440/1024/390px cover initial and selected-template states with no page errors, failed APIs or horizontal overflow. Backend source and document formatting were unchanged in this refinement.

The later document-first gallery correction supersedes the preceding side-by-side preparation layout and introduces the bounded shipped-thumbnail exception described above. Its verification passed 56 workspace tests, Ruff and 38 browser checks, with one optional real-model invocation skipped. The browser checks match all twelve thumbnail source definitions to the current API, verify PNG responses, direct use, image fallback, native upload focus, and actual manual Word export while the UI reports an unconfigured model through a controlled status response. The narrow production static mount is regression-tested so images and provenance JSON cannot silently fall through to SPA HTML.

The independent finish review inspected sixteen valid production-bundle captures across 1440/1024/390px, including initial, selected-file, filled, catalog, loading, empty, retryable failure and missing-image states, plus the twelve-page contact sheet. Its disposition was **ship at this bounded scope**. The reviewer marked document visibility, template-led hierarchy, redundant progress rail and explicit actions resolved; pre-file metadata remains a nonblocking tradeoff. Long selected-state pages, Word renderer/font differences and the skipped real-model invocation remain outside any claim of whole-product acceptance. Documentation reconciliation preserved all visual token values; shipped rasters are limited to the documented starter covers.

## Repository coordination

Per the coordinated migration decision, the destination repository is `https://github.com/otterview-labs/DocuGen`. Keep the current local `quill` directory and `QUILL_*` configuration compatible during migration. This change is committed locally; do not publish or recreate `otterview-labs/quill`. Repository history migration and public brand changes are handled separately.
