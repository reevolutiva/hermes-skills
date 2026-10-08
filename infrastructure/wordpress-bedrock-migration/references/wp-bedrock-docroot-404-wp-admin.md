# Bedrock mount/docroot mismatch (symptom: 404 on `/wp-admin/`)

## What it looks like
- You deploy WordPress (often **Bedrock**) behind an ingress.
- `GET /wp-admin/` (and sometimes `/wp/wp-admin/`) returns **404 Not Found** from the **web server** (LiteSpeed/OpenLiteSpeed).
- The underlying filesystem may still contain `wp-admin/` — meaning the **docroot configured in the web server doesn’t point to where you mounted/copy the WP core**.

## Likely root cause
Bedrock WordPress core arrives nested under an unexpected directory, e.g.:
- `/var/www/html/wp/web/wp/wp-admin/`
- `/var/www/html/wp/web/wp/wp-config.php`

…but the web server expects:
- `/var/www/html/wp-admin/`
- `/var/www/html/wp-config.php`

Additionally, when using **litespeedtech/openlitespeed** images, there’s a second common failure mode:
- You mount WP files into `/var/www/html` (Kubernetes `volumeMounts`),
- but the container’s default vhost docroot points elsewhere (commonly `$VH_ROOT/html` for a default vhost like `Example/`).
- In that case, **even a perfectly-mounted filesystem will still return 404**.

## Verification commands (run inside the running WP pod)
Use these in order: (1) check WP core presence in the filesystem, then (2) check the web server’s effective docroot.

### A) Confirm WP core exists where you mounted it
```bash
DOCROOT=/var/www/html

echo "--- Root contents ---"; ls -la "$DOCROOT" | sed -n '1,120p'

echo "--- Expected WP root checks ---";
for f in "$DOCROOT/wp-config.php" "$DOCROOT/wp-admin" "$DOCROOT/wp-includes" "$DOCROOT/index.php"; do
  if [ -e "$f" ]; then echo "OK: $f"; else echo "MISSING: $f"; fi;
done
```

### B) Search where the real WP core ended up
```bash
find "$DOCROOT" -maxdepth 6 -name wp-config.php -o -name wp-admin -o -name wp-includes 2>/dev/null | head -n 50
```

### C) OpenLiteSpeed/LiteSpeed: check vhost docroot vs your mount
Inside the pod, grep the configured vhost `vhRoot` and `docRoot`.

```bash
# Identify where docroot is configured
grep -Rni --max-count=80 -E "vhRoot|docroot|DocumentRoot|WebsiteRoot|vhdomain|vhDomain" /usr/local/lsws/conf 2>/dev/null || true

# The main config typically shows which vhost templates are used
ls -la /usr/local/lsws/conf
ls -la /usr/local/lsws/conf/httpd_config.conf* 2>/dev/null || true
```

A common pattern you may find:
- `vhRoot Example/`
- `docRoot $VH_ROOT/html/`

And then (crucially) verify that the effective docroot directory actually contains `wp-admin`:

```bash
# Replace the paths below with what you discovered via vhRoot/docRoot
# (the example assumes VH_ROOT corresponds to /usr/local/lsws/vhosts/Example)
EFFECTIVE_DOCROOT=/usr/local/lsws/vhosts/Example/html

ls -la "$EFFECTIVE_DOCROOT" 2>/dev/null || true
ls -la "$EFFECTIVE_DOCROOT/wp-admin" 2>/dev/null || echo "Missing: $EFFECTIVE_DOCROOT/wp-admin"
```

## Fix pattern (recommended)
### Case 1: Nested Bedrock layout mismatch
Use an `initContainer` (or a one-shot Job) to *flatten/copy* the nested bedrock core into the docRoot expected by the web server.

Example mapping when extracted core is under `wp/web/wp/`:
- Copy `wp/web/wp/wp-config.php` → `/var/www/html/wp-config.php`
- Copy `wp/web/wp/wp-admin/` → `/var/www/html/wp-admin/`
- Copy `wp/web/wp/wp-includes/` → `/var/www/html/wp-includes/`
- Copy `wp/web/wp/index.php` → `/var/www/html/index.php`

### Case 2: OpenLiteSpeed docroot doesn’t point to `/var/www/html`
When using the official OpenLiteSpeed container defaults, the most reliable options are:

1) **Mount into the effective docroot**
- Change the Kubernetes `volumeMount.mountPath` to match the effective vhost docroot you found (e.g. `/usr/local/lsws/vhosts/Example/html`).

2) **Or patch the LSWS vhost config**
- Update/replace `vhconf.conf` (or the relevant vhost configuration) so `docRoot` points to `/var/www/html`.

In both cases, re-verify the gate:
- `test -d <EFFECTIVE_DOCROOT>/wp-admin` must succeed.
- `test -e <EFFECTIVE_DOCROOT>/wp-config.php` must succeed.

## Kubernetes routing sanity checks (before blaming Cloudflare)
```bash
kubectl -n <ns> get ingress -o wide
kubectl -n <ns> get svc -o wide
kubectl -n <ns> get endpoints -o wide
kubectl -n <ns> get pods -o wide
```

## Gate before changing Cloudflare
If the docroot/WP-root checks show missing files **in the web server’s effective docroot**, do **not** tune Cloudflare yet—fix origin first.

---
### Session-specific note (this exact incident)
In this environment, `wp-admin/` existed under `/var/www/html`, but the web server returned 404 for `/wp-admin`.
That happened because the container vhost configuration still used the default vhost docroot (e.g. `vhRoot Example/` + `docRoot $VH_ROOT/html/`), not the mounted `/var/www/html`.

So: when you see `/wp-admin` 404 while `/var/www/html/wp-admin` exists, **assume vhost docroot mismatch first** and verify `vhRoot/docRoot`.
