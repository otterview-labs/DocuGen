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

Known inherited warnings include Starlette/AnyIO deprecation and Pydantic field-alias metadata warnings. They did not fail the verified checks.
