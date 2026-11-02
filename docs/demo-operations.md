# Recovering the public demo

The public demo has three dependencies: the DocuGen Compose stack, a reverse proxy that owns the
`docugen.otterview.ai` site, and DNS pointing to that proxy. A successful DNS lookup does not mean
the demo was restored after a server migration or reinstall.

## Before a migration

Record the reviewed source commit and built image digests, Compose project name and files, volume
names, loopback port, and the proxy site configuration. Back up the deployment environment file
through a private operations channel; never commit its values. Keep the proxy's certificate storage
and renewal configuration with the server backup. The demo's expiring visitor data is not a durable
user workspace; ordinary self-hosted deployments need their own backup process.

## Restore in dependency order

1. Restore the reviewed source and deployment environment file to a private release directory.
   Never copy an ordinary shared-workspace configuration into the anonymous public demo.
2. Validate and start only the demo project:

   ```bash
   docker compose -f compose.yaml -f deploy/compose.demo.yaml -p docugen-demo config --quiet
   docker compose -f compose.yaml -f deploy/compose.demo.yaml -p docugen-demo up -d --build --wait
   curl --fail http://127.0.0.1:18080/health
   ```

   `POSTGRES_PASSWORD` must be set privately. Use the deployment's recorded image override file
   as an additional `-f` argument when restoring prebuilt images. Preserve volumes; do not prune
   or run `down -v` as part of recovery.
3. Add the site from [`deploy/Caddyfile.demo`](../deploy/Caddyfile.demo) to the existing edge
   configuration, preserving the other sites. Back up, validate the entire configuration and
   reload Caddy. Check that the proxy can reach host loopback (for a containerized proxy this
   depends on its network mode). Do not publish engine or database ports to work around it.
4. Check the workspace's actual TCP peer after proxying. If Docker presents its dedicated bridge
   gateway, configure that exact address using `DOCUGEN_DEMO_TRUSTED_PROXY_IPS`; see the
   [trusted proxy instructions](PUBLIC_DEMO.md#trusted-proxy-address-behind-docker). Otherwise
   new visitors share a rate bucket. Keep the original request/session limits.
5. Verify DNS, trusted TLS and the public route:

   ```bash
   curl --fail https://docugen.otterview.ai/health
   ```

   A TLS alert before an HTTP response calls for checking the edge site and certificate issuance;
   it is not an application route error. A 502 calls for checking the private upstream and its
   health. A 429 is a sandbox quota/rate response; do not disable its limits to pass an acceptance
   check or repeatedly open fresh sessions from the same IP.
6. From `frontend/`, run the opt-in browser acceptance against this isolated demo:

   ```bash
   DOCUGEN_DEMO_URL=https://docugen.otterview.ai \
     npx playwright test e2e/public-demo.spec.js --reporter=line --workers=1
   ```

   This covers template filling, a real Word download, denial of another browser's generated
   file and knowledge resource, plus desktop/mobile navigation. A health-only check is insufficient.

After recovery, keep a private deployment manifest with the source commit, image IDs, release
path, proxy configuration/backup paths and verification result. Keep credentials and visitor data
out of that manifest. Include the demo explicitly in the next server migration inventory.

## Recovery verified 2026-11-02

The server no longer contained the former demo stack or site configuration after a reinstall.
The public demo was rebuilt from baseline `b9f5aeb`, started with its isolated Compose profile,
and its Caddy site restored alongside the existing sites. Follow-up checks exposed shared rate
attribution behind Docker DNAT; the exact trusted-proxy configuration in this change fixes it
without increasing limits. Fresh expiring demo storage was created; the old demo sessions were
not recovered. The private deployment manifest records the final deployed commit and checks.
