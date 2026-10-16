# Working on Quill

- This repository owns the Quill integration. Upstream source revisions and adaptations are recorded in `docs/PROVENANCE.md` and `docs/upstream.json`.
- Put workspace APIs, generation orchestration and persistence in `quill/`. Keep the knowledge engine under `services/knowledge/` behind the provider contract. Avoid importing its top-level `app` package into the Quill process.
- Preserve upstream attribution. Do not invent licensing terms for imported code; publication status is recorded in the provenance document.
- Keep `.env`, credentials, workspaces, generated documents, database files and customer templates out of Git. Use synthetic data in tests.
- The current product is a single shared workspace with one API worker. Do not claim separate user or tenant isolation.
- Provider failures must remain explicit; do not replace failed retrieval or generation with example output.
- Run Quill tests and Ruff for workspace backend changes. Run inherited engine tests in their own process for knowledge changes. Run the Vue build for frontend changes, and browser smoke checks for changed upload/download or navigation flows.
- No paid model calls are required for the normal test suite.
- Core UI controls use `frontend/src/components/ui/` and the canonical `frontend/src/styles/ui.css`. Page CSS may arrange shared controls, but must not redefine their font, color, radius, height or icon size. Use an explicit compact variant for compact toolbars, and match repeated actions across routes.
- Shared buttons default to `type="button"`; form submissions must explicitly use `type="submit"`. Preserve focus transfer/restoration and keyboard tab behavior when changing wrappers.
- Verify UI consistency with the cross-route computed-style browser checks as well as screenshots and functional flows. Keep DESIGN.md and its sidecar aligned with accepted shared-token changes; passing functional tests alone does not establish visual consistency.
