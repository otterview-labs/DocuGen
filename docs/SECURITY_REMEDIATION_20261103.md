# Security maintenance — 2026-11-03

The default workspace and knowledge text profile use patched FastAPI/Starlette, multipart, PDF, certificate, image, HTTP and XML dependencies. `uv.lock` records the workspace resolution. The optional/native profiles retain their purpose, with patched dependency floors; NLTK has no runtime imports and is no longer installed. The engine's JWT decoding now uses PyJWT with the configured algorithm allowlist, preserving invalid-token failures and valid signed-token handling. No credentials or customer data are required for tests.

File processing accepts local media only inside upload/download/temp storage roots. Paths are canonicalized before checking a separator-terminated root boundary, so sibling prefixes and symlinks outside storage fail. URL imports reject absolute paths, traversal components and backslashes before invoking parsers. Legacy frame downloads enumerate server-owned filenames rather than interpolating user input into glob expressions. FFprobe takes a validated absolute input path after `-i`; media frame-rate metadata is parsed numerically and never evaluated as Python code.

Regression tests cover normal files, nested paths, traversal, absolute sibling paths, symlinks, encoded download requests, rejected URL imports, media-tool arguments, valid JWTs, wrong signatures, expired tokens and unapproved algorithms.

Local verification: workspace tests and Ruff; knowledge-engine tests in a separate process; frontend clean install/build/npm audit; optional full profile dependency resolution for Linux x86_64 Python 3.11 and native profile resolution for Linux ARM64 Python 3.11. Resolution does not execute OCR/local transformer models or validate GPU runtimes. GitHub CodeQL/Dependabot results must be checked on the merged commit rather than inferred from local tests. No findings are dismissed merely to lower the count.

## Medium-severity follow-up

Public knowledge API errors now use stable messages instead of raw exceptions. Dependency health checks keep the dependency's failed status and log diagnostics privately. The legacy `/optimized_frames/{filename}` endpoint serves through the same contained-file handler as `/uploads/`, without creating a user-controlled redirect. CI requests only `contents: read`.

Container builds accept `SOURCE_REVISION` and record it in OCI image labels so a public demo can be checked against the reviewed commit. Existing anonymous-demo isolation, quotas and storage names remain in effect. README entry points now lead with the actual console, example workflows, demo and setup links; English remains the default.
