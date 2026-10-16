# Quill workspace UI

Vue workbench adapted from DocuGen, with knowledge collections/retrieval, document writing, template upload, variable editing and authenticated downloads. The interface currently uses Chinese.

Run the Quill API on loopback port 8080, then:

```bash
npm ci
npm run dev
```

The Vite development proxy forwards `/api` and `/download` to the local API. For the built-in backend UI, run `npm run build` and start Quill; the backend serves `dist/`.

The shared API key is entered in the header and kept in sessionStorage. It never goes into a download URL. All authorized visitors share the same workspace.

Browser checks run against an existing local service. With a root `.venv` and `.env` present:

```bash
QUILL_TEST_URL=http://127.0.0.1:8080 npx playwright test
```

Checks create an explicitly named test template, exercise upload/fill/download, and capture desktop/mobile writing pages. Artifacts are excluded from Git.
