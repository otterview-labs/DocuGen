# Local integration verification — 2026-10-16

Verified on the local development host. These are local results; no GitHub Actions run or public deployment is implied.

| Check | Result |
| --- | --- |
| Quill unit, API, file parsing and provider contract tests | 25 passed |
| Imported knowledge tests, including a clean-database bootstrap check and resource management | 89 passed |
| Ruff for Quill API, tests and native startup script | Passed |
| Vue production build | Passed with Vite 8 |
| npm audit | 0 reported vulnerabilities at verification time |
| Browser template upload → variable entry → Word download | Passed |
| Desktop 1440px and mobile 390px navigation/layout | Passed; all four navigation entries visible, no page overflow |
| Browser knowledge workflow | Passed: create, import TXT, deduplicate, preview/segments, edit metadata, download original, keyword search/source navigation, delete |
| Source navigation focus | Passed: preview receives focus on entry, close returns to the source after metadata reload; mobile preview focus checked |
| Knowledge screen capture matrix | Management, source preview and search captured at 1440px and 390px; synthetic fixtures explicitly labeled |
| PDF/DOCX parsing | Real PDF text extraction, scanned-PDF rejection, DOCX paragraph/table order, Chinese encoding and invalid file cases passed |
| Missing embedding configuration | HTTP 409 through the real engine/gateway; no invented localhost embedding endpoint |
| Real native knowledge API → text ingestion → keyword retrieval | Passed using SQLite |
| Docker workspace, knowledge engine, PostgreSQL/pgvector startup | All three services healthy |
| Real Docker-backed collection creation, text persistence and retrieval through Quill | Passed |
| Updated Docker-backed file workflow | PDF and DOCX import/deduplication/preview/metadata update, byte-exact original downloads, keyword source results, 409 missing-model feedback, 401 download protection and deletion passed; temporary resources removed |
| Real Docker-backed template upload, rendering, authenticated download | Passed; downloaded Word content reopened and checked |
| Unauthenticated data access | HTTP 401 |
| Document generation with no configured model | HTTP 503; no placeholder document returned |
| Staged credential-pattern scan and Git exclusions | No matching real-key patterns; runtime config, data and dependencies excluded |

The Docker build initially encountered a dependency-download DNS failure. A retry succeeded. The deployed port is loopback-only 8080. Synthetic example material is explicitly named as examples in the local runtime and is not committed.

The generation pipeline is exercised with controlled model responses in tests. A real model/provider was not configured or called. Therefore real model quality, semantic embedding quality, token costs, citations at sentence level, and complex Word layout fidelity have not been accepted. OCR/video/graph parsers and multi-user isolation are outside this verification scope.

In the initial reading-workbench iteration, six browser cases passed across the bounded capture and correction runs. A new focus-restoration assertion exposed row replacement during metadata refresh; stable resource-based restoration was added and the complete management workflow then passed. The independent design reviewer scored all three requested fixes resolved and returned `ship` for that fix list. This is not an independent review of backend model quality.

## Reference-driven UI refinement

The subsequent user request supplied VoltAgent/awesome-design-md. Sources, exact reference revision and application boundaries are recorded in [UI_REFERENCES.md](UI_REFERENCES.md).

- Vue production build passed; no new production dependency was added.
- All 11 Playwright cases passed in the first batched inspection and again in the single correction/confirmation run.
- The matrix covers 1440px, 1024px and 390px. Knowledge management, source preview and search account for nine captures; catalog, upload/variable entry, template generation and writing account for twelve captures. No horizontal page overflow or browser exceptions were observed.
- Real template upload, manual variable filling and authenticated DOCX downloads passed through both template entry paths. Catalog search, list/grid switching and keyboard entry passed. The existing knowledge import, deduplication, metadata, source focus/return and deletion workflow passed.
- Shared field text uses explicit normal weight; source prose uses 15px ink text; the mobile primary retrieval action is at least 44px high. Breadcrumb computed foreground is `rgb(102, 115, 107)` on `rgb(252, 252, 247)`.
- The single design-detector scan returned no findings. No model was called. Backend code and model contracts were unchanged in this refinement.
- The independent full review accepted the preserved workbench and all 21 captures. A breadcrumb contrast finding was withdrawn after verifying the actual cascade. The final verdict returned `ship` for the canonical breadcrumb declaration, regular field weight and mobile retrieval-control correction batch, with no observed regressions within that scope.

## Canonical control correction after user feedback

The user rejected the earlier visual-unity claim and specifically identified buttons, typography and colors. This correction replaces page-specific implementations with shared Vue components and a single primitive stylesheet; it does not imply that the entire product is ready for an open-source release.

All 17 browser cases passed in the final correction/confirmation run. In addition to the existing workflows and capture matrix, checks cover computed font family, size, weight, semantic color, radius, height and icon geometry; repeated AI-fill action parity; keyboard tab navigation; and explicit form submission. Outline/job responses are controlled in the submission test, so no paid model is called. Backend code and contracts were unchanged.

| Viewport | Routes checked | Visible button instances across routes | Button type / weight / radius | Heights | Working font families |
| --- | --- | --- | --- | --- | --- |
| 1440px | 5 | 37 | 13px / 500 / 6px | 40px standard, 32px compact | 1 |
| 1024px | 5 | 37 | 13px / 500 / 6px | 40px standard, 32px compact | 1 |
| 390px | 5 | 37 | 13px / 500 / 6px | 44px standard, 40px compact | 1 |

Fifteen field instances across the five routes were checked at each width: 14px regular text at desktop/tablet and 16px on mobile, using the same inherited working family and ink role. Source-preview focus, manual DOCX upload/fill/download and knowledge management continued to pass.

The fresh independent full review found seven bounded corrections. The single correction batch restored field/action gaps, normalized native control font inheritance and repeated AI-fill sizing, corrected highlighted-text contrast, padded retrieval controls, restored shell colors and synchronized design documentation. The same 21 captures were confirmed after correction. One detector scan returned no findings; no second scan was run.

The final independent verdict scored all seven fixes resolved and returned `ship` for that correction list, with no material regression observed in the recaptures. The deployed 8080 template page was also checked for the canonical 40px/13px/500/6px primary action. Existing persisted collection and template counts remained unchanged; test fixtures stayed in an isolated runtime.

A subsequent deployed acceptance check exposed a shared link-wrapper regression: forwarding an undefined `href` to RouterLink removed its native anchor destination. Mutually exclusive prop binding corrected the wrapper, and a new regression checks link role, actual `href` and Enter navigation for upload, return and template-use actions. All ten noncapture browser cases passed after this functional fix, including the existing workflows and computed contracts. The preceding 17-case full run and 21 confirmed captures remain the visual evidence; the link fix changed no CSS and generated no further screenshots. On the rebuilt 8080 runtime, the upload action retained its canonical metrics and `/create` destination, and keyboard navigation passed. Persisted counts remained one collection and one template.

Known inherited warnings include Starlette/AnyIO deprecation and Pydantic field-alias metadata warnings. They did not fail the verified checks.

## Knowledge capability expansion — 2026-10-17

- Audited the running engine OpenAPI and source registration: 51 distinct mounted knowledge paths are mapped to existing product tasks or 28 new named operations. Compatibility aliases share one task. Full mapping and unmounted-module boundaries are in [KNOWLEDGE_CAPABILITIES.md](KNOWLEDGE_CAPABILITIES.md).
- Workspace tests: 30 passed; Ruff passed. Engine tests: 90 passed, including real SQLite persistence of QA, resource/content identifiers, status, saved tags, actual chunk records, collection settings, and dependent-record cleanup.
- Four new browser workflows cover actual single/batch QA imports with partial failure, authenticated templates, stored chunks, saved analysis, status, collection settings/deletion confirmation, metadata prefilling, advanced keyword sources/preview, staged upload/parse/task history and byte-exact original downloads. Graph rendering uses an explicitly labeled controlled response. Together with existing functional and computed-control checks, the final noncapture run passed all 14 cases. Computed controls were checked at 1440px, 1024px and 390px.
- The bounded visual inspection and confirmation used the same 14 captures: document management, QA form, stored chunks, missing-graph state, detailed metadata, advanced source results and synthetic graph, each at 1440px and 390px. No horizontal page overflow or browser exception was recorded. One detector returned `[]`; no second detector ran. The fresh independent finish reviewer opened all originals, returned `ship` for this knowledge extension, and found no material fixes. The documenter verified existing design-system ownership without changing DESIGN.md or its sidecar.
- Rebuilt Docker workspace/engine and checked the real PostgreSQL/pgvector deployment through authenticated port 8080 APIs. All 28 catalog operations registered. Actual single/batch QA, keyword exclusion after disable, metadata/tags/relations, collection model records, stored chunks and strategies passed. Direct upload, staged-file parsing and batch parsing completed on TXT; authenticated original downloads matched input bytes. Missing graph/embedding prerequisites returned explicit 409s and deletion required confirmation. Temporary collection records were removed; persisted collection/template counts remained 1/1.
- The expansion repairs missing aiohttp route registration, resource/content-ID mismatch, QA collection associations, ignored collection-model records, saved-tag decoding, parser-temp original loss and dependent chunk/relation removal. Runtime configuration and customer content were not copied into Git.

No paid provider was called. These checks do not accept real LLM/embedding/VLM output quality, semantic relevance, OCR/audio/video parser installation, actual graph-store behavior or multi-user isolation. Declared parser formats and configured flags are not claims of provider health. Batch progress remains process-local and browser task history is session-local.

## Full knowledge task polish — 2026-10-17

The polish preserves the Reading Workbench palette, typography and canonical controls across knowledge, writing and template routes. Changes cover all seven knowledge tabs and 28 operation entries, compact desktop form grouping, mobile operation disclosure with heading focus, the shared Chinese native file picker, technical-result disclosures and graph relationship labels.

- Vue production build passed with no added production dependency. The final assets are `index-CBgGzTEP.css` and `index-D1lV69Yj.js`.
- All 17 noncapture browser cases passed in the confirmation run (12.1 seconds). The new checks traverse all 28 forms at 1440px and 390px, verify mobile disclosure/focus, and drag/drop an actual synthetic QA JSON file through the native required file input and import it. Existing workflows and computed-control checks across five routes at 1440px, 1024px and 390px also passed. The advanced-source test now creates and removes its own collection and content rather than relying on a default collection.
- The bounded visual matrix contains 16 captures: documents, empty file picker, QA form, actual stored chunks, missing-graph state, metadata, advanced source results and explicitly labeled synthetic graph, each at 1440px and 390px. All originals were inspected; the capture report records no browser exceptions or page overflow. One detector returned `[]`; no additional detector ran.
- The fresh independent full finish review accepted the overall refinement and requested one bounded selected-collection metadata contrast correction. It now uses the canonical accent on the soft-green selection fill (5.87:1). The same two documents captures were updated; the final reviewer scored the fix resolved and returned `ship` for that correction list, with no observed regression.
- Rebuilt only the Docker workspace and performed read-only acceptance at port 8080 at 1440px and 390px: current assets loaded; 28 registered operations, Chinese native file input, mobile operation selection/focus, selected-metadata computed color and no overflow/browser exception were confirmed. Persisted collection/template counts remain 1/1. Test writes stayed in the isolated runtime.

Backend source and contracts did not change during this polish, so the preceding backend suites were not rerun. No paid model or actual graph store was exercised; synthetic graph evidence remains explicitly labeled. The UI acceptance does not extend the provider-quality or installation scope recorded above.

## Current-runtime acceptance audit — 2026-10-18

The user asked whether every function had been verified without problems. The answer is **no**: automated regression success, UI reachability and registered capabilities do not establish complete real-provider acceptance.

- Reran workspace tests: 30 passed. The initial attempt encountered the host's SOCKS proxy environment without the optional `socksio` package; a command-scoped run with proxy variables removed passed. No application code or global environment was changed. Reran engine tests in their own process: 90 passed. Existing deprecation/field-alias warnings remain.
- Docker workspace, knowledge and PostgreSQL services are healthy. Authenticated status reports no generation model. The knowledge catalog reports LLM, embedding and graph configuration all false. Of 28 named operations, 19 pass the registration/configuration gate and nine are unavailable: analysis generation, vector reindexing and the seven graph tasks. This gate is not a successful execution or parser-installation check; advanced retrieval modes can have additional prerequisites.
- Read-only browser checks at port 8080 passed the existing desktop/mobile deployment assertions (1440px/390px, current assets, catalog count, file picker, mobile disclosure/focus, selection color, no page exceptions or overflow). Four routes—templates, knowledge, writing and template upload—were also checked in fresh browser contexts: authenticated initial API requests succeeded without page exceptions; without a key they returned 401. This confirms that the manual access-key requirement remains present and has not been replaced by local automatic access or account login.
- Persisted collection/template counts remain 1/1; no deployed data was written and no provider was called. This audit does not rerun the earlier 17-case write-flow browser suite or visual capture matrix; those remain dated evidence from the previous section.

Still unaccepted: real AI writing/QA and automatic template filling; embedding generation, semantic retrieval quality and vector indexing; actual graph database execution; optional OCR/audio/video parsers; and complex Word-layout fidelity. Model/provider configuration and the access-key UX remain outstanding product work, not completed features inferred from these checks.

## Key-free local access and real local-model verification — 2026-10-18

The user requested actual verification and removal of the local workspace key requirement. Compose now accepts an empty `QUILL_API_KEY`; the local runtime clears that key, and the shell hides connection settings after a successful status response reports authentication disabled. A protected deployment still displays its connection form after a 401 and retains API/download enforcement. Existing shared controls and CSS geometry are unchanged.

- Workspace tests: **35 passed**; Ruff passed. New checks cover empty/key-enabled access through actual template upload, render and DOCX download, incorrect/absent keys on protected downloads, stale saved keys in local mode, keyless provider requests, optional reasoning parameters and rejection of reasoning-only empty answers. The command-scoped test run removed host proxy environment variables as in the preceding audit. Engine tests: **90 passed** in their independent process; inherited warnings remain.
- Full browser regression against an isolated Docker workspace/knowledge/PostgreSQL stack: **28 passed in 38.3 seconds**, including an explicitly enabled real local-model UI test. This includes the existing import/deduplication, source focus, QA/status/settings/metadata, parse progress, downloads, 28-form reachability, keyboard navigation and shared-style checks at 1440px/1024px/390px. Fresh pages/new tabs/reloads use no saved key or Authorization header; a controlled 401 confirms that protected-mode connection settings remain reachable. The first run found a test step that attempted to click task tabs behind the intentional tablet preview drawer; the test now closes and verifies closure of the preview before switching tasks.
- Supplemental real API execution covered **all 19 configuration-available named operations**, using synthetic collections, including direct/staged/batch TXT parsing, real task completion and markdown, QA import, existing analysis/chunks, metadata/status, collection settings, keyword retrieval and deletion. Each of the **nine unavailable operations returned its declared 409**. Unconfigured semantic/graph search returned 409; before enabling the workspace model, job creation returned 503 and outline generation returned an explicit missing-model error. PDF, DOCX, TXT, Markdown, CSV and JSON all passed import, deduplication and byte-exact original-download checks against the isolated real engine.
- Discovered an existing host-local Ollama service and installed `qwen3.6:27b` model. No model was downloaded and no cloud provider or paid API was used. The initial default-thinking request used its short output budget on reasoning and produced no answer; optional `QUILL_LLM_REASONING_EFFORT=none` produced a normal answer and is covered by contract tests. Empty default settings omit the parameter for other providers. AI template-fill browser requests now use the same 180-second allowance as other model operations, accommodating cold starts.
- Real-model API checks passed with synthetic facts: keyword-sourced knowledge answer contained the expected 30-day period and a `[1]` citation backed by the saved resource ID (4.22 seconds); AI template variables matched the supplied project and owner and rendered a valid DOCX (5.01 seconds); a real outline returned eight headings (8.06 seconds); a generation job completed, exported a readable DOCX and retained its source records (4.67 seconds). The additional browser case independently clicked AI fill, confirmed both variables, downloaded its Word, generated an outline, submitted a real job, observed completion/source records and downloaded that Word. These timings are warm-run observations, not a performance guarantee.
- Updated the local workspace to the existing host model, without either a workspace access key or model API key. Read-only acceptance at **8080** passed five routes at 1440px and 390px, including a reload and a fresh session with no saved key: current assets loaded, `authentication=false`, `model_configured=true`, no failed initial API requests, no page exceptions and no overflow. Persisted collection/template counts remain **1/1**; deployed content was not used in model verification or written by the tests.
- Standard Docker build hit an upstream registry metadata timeout. Deployment used the existing local application image as its dependency base, copied the freshly built Vue assets and current Quill backend into a new image, and recreated only the workspace. No dependency change was required. Normal source Dockerfile remains the reproducible build definition. Final Vue assets are `index-CBgGzTEP.css` and `index-DuodJm1I.js`.

The real-model acceptance above supersedes the preceding audit's untested status for these bounded workspace generation flows. It does not establish universal factual accuracy, business-template layout fidelity, vector/semantic relevance or optional parser health. Knowledge-engine generation configuration remains separate from the workspace's successful local model calls; its nine gated analysis/reindex/graph operations are still unavailable in the current engine profile. Vector indexing, actual graph storage and OCR/audio/video execution remain unaccepted. The ordinary regression suite keeps real-model calls opt-in through `QUILL_REAL_LOCAL_MODEL=1` and must target isolated test data.
