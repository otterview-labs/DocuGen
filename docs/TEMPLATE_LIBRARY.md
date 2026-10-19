# Template library and DocuGen comparison

The template flow now includes twelve original starter templates, distinct from uploaded workspace files. Their content definitions and DOCX formatting are in `quill/template_library.py`; no customer or archived runtime documents are bundled.

The compared DocuGen snapshot is `BetaStreetOmnis/DocuGen@5c2799899abcfba6d1aecd0b0a340ecca5b04e71`. Its Vue catalog has category filters, search, grid/list presentation and a template API. The tracked `templates/` directory contains two Word files (`1212.docx`, `投标文件.docx`). The snapshot's `app.py` references a `template_store` module not present in that tree. This evidence does not establish how many uploaded templates existed in the previous running deployment. Those runtime files have not been migrated or replaced by the starter library.

## User flow

- `/templates` combines workspace files and the starter library, with separate source tabs. Workspace files come first in the combined view. Search includes template names, descriptions and variable names; category choices reflect the current source's actual records. Grid/list and pagination remain available.
- Starter entries show actual section names from the same definition that builds the Word file. “查看结构” opens an inline structure preview, explicitly distinguished from Word pagination. Keyboard focus moves into the preview and returns on close; Escape closes it.
- Original starter DOCX files download without model setup or installation. “使用模板” stores one editable workspace copy and opens the existing variable editor. Installation is idempotent, survives restarts, and chooses another name when a custom upload already owns the default name. Existing workspace metadata and files are preserved.
- `/create` offers an explicit library entry and accepts a category and description for custom uploads. Generated documents continue to use the uploaded DOCX's original styles. Starter copies use A4, a title, a metadata table, headings, a header and a PAGE field.
- Manual filling and export require no model or API key in the local deployment. AI filling retains the existing model dependency.

## Templates

项目实施方案、技术方案、运维服务方案、项目验收报告、工作周报、会议纪要、项目进展报告、商务报价单、投标响应文件、个人简历、商务函件、需求说明书。

These are reusable content frameworks with a consistent base Word layout. They are not recreations of the previous deployment's templates or twelve unrelated visual themes. Download and edit the DOCX in Word to create another layout, then upload it as a workspace template.

## Validation

Backend coverage downloads, installs, fills and reads all twelve actual DOCX files. It checks values, multiline content, placeholder removal, title/table/heading styles, page size, headers and PAGE fields, plus authorization, invalid identifiers, repeated installation and same-name preservation. Browser coverage exercises the complete starter flow, original download, generation, source filters, custom upload metadata, keyboard focus and 1440/1024/390px layouts. Existing cross-route control checks continue to apply.

Validation result: 55 workspace tests and Ruff passed; the full browser suite passed 33 tests, with the explicitly opt-in real-model test skipped in this run. The downloaded project-plan DOCX was rendered and visually inspected: one readable page, black title without the inherited blue rule, correctly proportioned information table, six sections, header and page number. Browser captures are local test artifacts, not shipped raster assets. Knowledge-engine source was unchanged.

## Repository coordination

Per the coordinated migration decision, the destination repository is `https://github.com/otterview-labs/DocuGen`. Keep the current local `quill` directory and `QUILL_*` configuration compatible during migration. This change is committed locally; do not publish or recreate `otterview-labs/quill`. Repository history migration and public brand changes are handled separately.
