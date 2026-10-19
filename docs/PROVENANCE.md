# Source provenance and publication status

## DocuGen integration, 2026-10-19

The project owner chose **Otterview DocuGen** as the public product name. This repository integrates the former Quill workspace while retaining the original DocuGen and Quill Git histories. The original DocuGen tree is preserved on `legacy/docugen-20261019` and `docugen-legacy-20261019`; the former Quill 0.1.0 release is preserved under `quill-v0.1.0`. Earlier entries below describe the source imports and verification under the Quill name. The previously confirmed Apache-2.0 release authorization and original attribution remain in force for the integrated adaptations.

Only committed source is integrated. Runtime workspaces, credentials, customer templates and generated artifacts are excluded. Existing installations retain their runtime namespace and data/volume names.

## Earlier Quill source records

This is a new local repository assembled for Otterview Quill on 2026-10-16. Exact upstream revisions are recorded in [upstream.json](upstream.json).

| Source | Imported material | Treatment |
| --- | --- | --- |
| `jetlinks-v2/jetlinks-knowledge-runtime`, `73eaa749472e9b0263d3d66d22917aa67528cffe` | Committed `app/`, tests, entry point, dependency manifests | Imported into `services/knowledge`. Working-tree changes in the original checkout are excluded. Added a Quill ingestion route and changed the API title. |
| `BetaStreetOmnis/DocuGen`, `5c2799899abcfba6d1aecd0b0a340ecca5b04e71` | Vue frontend; selected template extraction/replacement and Word rendering methods | Frontend adapted in place. Reusable Python methods extracted into `quill/legacy` with explicit output directories; old model clients, servers and EasyRAG connector excluded. |

Neither source's credentials, `.env`, working data, generated documents, runtime databases, or Git history is included. The new local `.env` is excluded by `.gitignore` and is not part of the repository content. Source services are independent directories, not embedded Git repositories or submodules.

## Attribution and license boundary

The imported code retains its upstream authorship. The inspected snapshots do not include a root LICENSE file establishing reusable terms for all imported code. A DocuGen README license badge is not a substitute for a license grant, and moving JetLinks source into a new organization does not itself grant a new license.

On 2026-10-19, the project owner explicitly confirmed that both imported source trees are authorized for public release. The Quill release uses Apache-2.0 for the project and these authorized adaptations; see the root `LICENSE` and `NOTICE`. Original authorship and the exact source revisions remain recorded here. The missing license files in the earlier snapshots are historical provenance, not a claim that unrelated upstream repositories, dependencies, model weights or data receive a new license.

Inherited trailing whitespace is normalized. Integration fixes include portable inherited test paths, non-conflicting operation-log index names, removing accidentally inherited composite integer primary keys from batch models, bounded Word placeholder replacement, and a proper Word TOC field without a leading blank cover page.

The knowledge-workbench increment adds private Quill resource-management routes, file metadata/deduplication and explicit reindexing. It removes the engine's invented localhost embedding fallback when no local embedding endpoint is configured. The Vue shell and knowledge surface are replaced with the Quill reading workbench; inherited template/rendering attribution is retained. Gateway PDF/DOCX text extraction and private original storage are new Quill integration code.

## Intentionally excluded

- Source deployment scripts, server addresses, operational reports, local configs and `.env` files.
- Production templates, customer materials and historical generated files.
- DocuGen's missing `template_store` import, example-only generation endpoints, global model switch and in-memory legacy server state.
- Unrelated keyword-generation test scripts in DocuGen.
- Legacy static administration pages from the knowledge runtime; its JSON API is the integration surface.

The upstream heavy parsing dependency manifests remain for reference. Only the Quill text engine dependency profile is used by the new Compose service. Additional parser profiles require their own compatibility verification.

The 2026-10-17 capability expansion adapts collection-aware QA import, resource/content-ID handling, collection model records, saved-tag decoding, original-file retention and dependent-record cleanup in the imported engine. It adds a private capability/chunk contract and an authenticated allowlisted Quill bridge; mounted endpoint-to-page mappings are in [KNOWLEDGE_CAPABILITIES.md](KNOWLEDGE_CAPABILITIES.md). Upstream authorship and the license boundary above remain in force.

The 2026-10-19 template correction extends the adapted DocuGen renderer to traverse existing headers, footers and nested table paragraphs consistently for variable extraction, AI reference text and rendering. The original attribution remains in the adapted source. It preserves existing run formatting and Word fields rather than replacing whole paragraphs. Public-release authorization is recorded above separately from this technical change.

The subsequent hands-on correction adds whitespace-tolerant placeholder matching against the original paragraph text, preventing inserted literal placeholder-like values from being expanded again. Quill adds a protected template-variable refresh operation and bounded field-name retrieval when full-template retrieval has no hits. These integration adaptations retain upstream attribution and the same publication terms.
