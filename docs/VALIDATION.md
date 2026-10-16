# Local integration verification — 2026-10-16

Verified on the local development host. These are local results; no GitHub Actions run or public deployment is implied.

| Check | Result |
| --- | --- |
| Quill unit, API and provider contract tests | 10 passed |
| Imported knowledge tests, including a clean-database bootstrap check | 87 passed |
| Ruff for Quill API, tests and native startup script | Passed |
| Vue production build | Passed with Vite 8 |
| npm audit | 0 reported vulnerabilities at verification time |
| Browser template upload → variable entry → Word download | Passed |
| Desktop 1440px and mobile 390px navigation/layout | Passed; all four navigation entries visible, no page overflow |
| Real native knowledge API → text ingestion → keyword retrieval | Passed using SQLite |
| Docker workspace, knowledge engine, PostgreSQL/pgvector startup | All three services healthy |
| Real Docker-backed collection creation, text persistence and retrieval through Quill | Passed |
| Real Docker-backed template upload, rendering, authenticated download | Passed; downloaded Word content reopened and checked |
| Unauthenticated data access | HTTP 401 |
| Document generation with no configured model | HTTP 503; no placeholder document returned |
| Staged credential-pattern scan and Git exclusions | No matching real-key patterns; runtime config, data and dependencies excluded |

The Docker build initially encountered a dependency-download DNS failure. A retry succeeded. The deployed port is loopback-only 8080. Synthetic example material is explicitly named as examples in the local runtime and is not committed.

The generation pipeline is exercised with controlled model responses in tests. A real model/provider was not configured or called. Therefore real model quality, semantic embedding quality, token costs, citations at sentence level, and complex Word layout fidelity have not been accepted. OCR/video/graph parsers and multi-user isolation are outside this verification scope.

Known inherited warnings include Starlette/AnyIO deprecation and Pydantic field-alias metadata warnings. They did not fail the verified checks.
