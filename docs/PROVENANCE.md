# Source provenance and publication status

This is a new local repository assembled for Otterview Quill on 2026-10-16. Exact upstream revisions are recorded in [upstream.json](upstream.json).

| Source | Imported material | Treatment |
| --- | --- | --- |
| `jetlinks-v2/jetlinks-knowledge-runtime`, `73eaa749472e9b0263d3d66d22917aa67528cffe` | Committed `app/`, tests, entry point, dependency manifests | Imported into `services/knowledge`. Working-tree changes in the original checkout are excluded. Added a Quill ingestion route and changed the API title. |
| `BetaStreetOmnis/DocuGen`, `5c2799899abcfba6d1aecd0b0a340ecca5b04e71` | Vue frontend; selected template extraction/replacement and Word rendering methods | Frontend adapted in place. Reusable Python methods extracted into `quill/legacy` with explicit output directories; old model clients, servers and EasyRAG connector excluded. |

Neither source's credentials, `.env`, working data, generated documents, runtime databases, or Git history is included. The new local `.env` is excluded by `.gitignore` and is not part of the repository content. Source services are independent directories, not embedded Git repositories or submodules.

## Attribution and license boundary

The imported code retains its upstream authorship. The inspected snapshots do not include a root LICENSE file establishing reusable terms for all imported code. A DocuGen README license badge is not a substitute for a license grant, and moving JetLinks source into a new organization does not itself grant a new license.

This repository therefore does **not** assign a blanket MIT/Apache license to upstream code. Before publishing as an open-source release, confirm the applicable terms or obtain authorization from the relevant rights holders, choose the intended license for new Quill code, and include the required license texts and attribution. No public repository has been created by this local integration.

Inherited trailing whitespace is normalized. Integration fixes include portable inherited test paths, non-conflicting operation-log index names, removing accidentally inherited composite integer primary keys from batch models, bounded Word placeholder replacement, and a proper Word TOC field without a leading blank cover page.

The knowledge-workbench increment adds private Quill resource-management routes, file metadata/deduplication and explicit reindexing. It removes the engine's invented localhost embedding fallback when no local embedding endpoint is configured. The Vue shell and knowledge surface are replaced with the Quill reading workbench; inherited template/rendering attribution is retained. Gateway PDF/DOCX text extraction and private original storage are new Quill integration code.

## Intentionally excluded

- Source deployment scripts, server addresses, operational reports, local configs and `.env` files.
- Production templates, customer materials and historical generated files.
- DocuGen's missing `template_store` import, example-only generation endpoints, global model switch and in-memory legacy server state.
- Unrelated keyword-generation test scripts in DocuGen.
- Legacy static administration pages from the knowledge runtime; its JSON API is the integration surface.

The upstream heavy parsing dependency manifests remain for reference. Only the Quill text engine dependency profile is used by the new Compose service. Additional parser profiles require their own compatibility verification.
