# Quill product context

Confirmed: Otterview Labs project, named Quill, combining JetLinks knowledge capabilities and DocuGen document generation into a new local repository under open-source/quill.

The first delivery is a functional integration for a single shared workspace. Users import and organize source files, inspect extracted content, retrieve facts, fill Word templates and generate documents with source records. Following the initial integration, the user requested a richer knowledge workflow and a full visual upgrade. The knowledge surface and shared shell use the user-confirmed reading workbench direction. A subsequent user request to reference VoltAgent/awesome-design-md extends the same visual system to writing, template browsing, upload/variable entry and template-based generation; existing backend contracts remain in use.

Assumptions for this first iteration: Chinese interface, local/self-hosted use, manual confirmation of generated documents, no independent user accounts. No claim of production hardening or public licensing readiness is implied.

The user subsequently rejected the claim of visual unity and identified buttons, typography and colors as the concern. Core routes now use shared Vue controls, page headers, notices, empty states and tabs. Canonical visual properties live in `frontend/src/styles/ui.css`; page styles arrange these controls without redefining their appearance. Cross-route computed-style checks supplement functional and visual checks. This acceptance scope concerns the inspected core routes, not a declaration that the entire open-source product is release-ready.
