/**
 * CloudFront Function (cloudfront-js-2.0): EdgeHostRouter — public site path rewrite.
 * docs/SPEC.md §3 Module 1C. KVS: 9host-site-hosts-kvs (HostMappingKVS).
 *
 *   /site/{tenant}/{site_id}/...  (backward compatible)  -> /{tenant}/{site_id}/published/current/...
 *   Host or X-Forwarded-Host (Cloudflare SaaS Worker) looked up in KVS:
 *     "<host>" -> {"tenant","site_id"}                    -> /{tenant}/{site_id}/published/current/...
 *   Unmapped hosts pass through unchanged.
 *
 * Directories resolve to index.html; extensionless paths to {path}/index.html.
 */
import cf from 'cloudfront';

var kvsHandle = null;
try {
    kvsHandle = cf.kvs();
} catch (e) {}

function resolvePath(p) {
    if (!p || p === '/') return '/index.html';
    if (p.endsWith('/')) return p + 'index.html';
    var last = p.substring(p.lastIndexOf('/') + 1);
    if (last.indexOf('.') === -1) return p + '/index.html';
    return p;
}

function headerValue(headers, name) {
    var h = headers[name];
    return (h && h.value) ? String(h.value) : '';
}

async function handler(event) {
    var request = event.request;
    var headers = request.headers || {};
    var uri = request.uri || '/';

    // 1. Backwards-compatible explicit /site/{tenant}/{site_id}/... path
    var siteMatch = uri.match(/^\/site\/([a-z0-9_-]+)\/([a-zA-Z0-9_-]+)(\/.*)?$/);
    if (siteMatch) {
        request.uri = '/' + siteMatch[1] + '/' + siteMatch[2] + '/published/current' + resolvePath(siteMatch[3] || '/');
        return request;
    }

    // 2. Effective hostname: X-Forwarded-Host (Cloudflare for SaaS Worker) or Host
    var host = headerValue(headers, 'host').toLowerCase().split(':')[0];
    var fwdHost = headerValue(headers, 'x-forwarded-host').toLowerCase().split(',')[0].trim().split(':')[0];
    var effectiveHost = fwdHost || host;

    // 3. Resolve {tenant, site_id} via CloudFront KeyValueStore (get() throws on a missing key)
    if (kvsHandle && effectiveHost && effectiveHost.indexOf('__') !== 0) {
        try {
            var raw = await kvsHandle.get(effectiveHost);
            if (raw) {
                var mapping = JSON.parse(raw);
                if (mapping && mapping.tenant && mapping.site_id) {
                    request.uri = '/' + mapping.tenant + '/' + mapping.site_id + '/published/current' + resolvePath(uri);
                    return request;
                }
            }
        } catch (err) {}
    }

    return request;
}
