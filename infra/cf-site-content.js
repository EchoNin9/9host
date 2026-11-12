/**
 * CloudFront Function (cloudfront-js-2.0): EdgeHostRouter — public site path rewrite.
 * docs/SPEC.md §3 Module 1C. KVS: 9host-site-hosts-kvs (HostMappingKVS).
 *
 *   /site/{tenant}/{site_id}/...  (backward compatible)  -> /{tenant}/{site_id}/published/current/...
 *   Host or X-Forwarded-Host (Cloudflare SaaS Worker) looked up in KVS:
 *     "<host>" -> {"tenant","site_id"}                    -> /{tenant}/{site_id}/published/current/...
 *
 * X-FORWARDED-HOST TRUST (T-18): once the KVS key "__proxy_secret__" exists, X-Forwarded-Host
 * is only honoured when the request also carries X-9host-Proxy-Secret equal to it (sent by
 * infra/cloudflare-worker/custom-domain-proxy.js from its PROXY_SECRET Worker secret);
 * otherwise the Host header is used. While the key is absent (rollout), X-Forwarded-Host is
 * trusted as before. The secret header is removed from the request either way.
 *
 * FAIL CLOSED: a request is only ever forwarded to S3 after being rewritten under
 * /{tenant}/{site_id}/published/current/. Unmapped hosts, missing/failing KVS,
 * malformed mappings and any URI containing a ".." segment (raw or %2e-encoded)
 * get a generated 404 — the original URI is never passed through, so draft/ and
 * published/v{N}/ keys are unreachable from this behaviour.
 *
 * Directories resolve to index.html; extensionless paths to {path}/index.html.
 */
import cf from 'cloudfront';

var PROXY_SECRET_KEY = '__proxy_secret__';
var PROXY_SECRET_HEADER = 'x-9host-proxy-secret';

var TENANT_RE = /^[a-z0-9_-]+$/;
var SITE_RE = /^[a-zA-Z0-9_-]+$/;

var kvsHandle = null;
try {
    kvsHandle = cf.kvs();
} catch (e) {}

function notFound() {
    return {
        statusCode: 404,
        statusDescription: 'Not Found',
        headers: {
            'content-type': { value: 'text/plain; charset=utf-8' },
            'cache-control': { value: 'no-store' }
        },
        body: 'Not Found'
    };
}

// True if any path segment is "..", after normalising %2e / %2f / %5c / backslash.
function hasDotDotSegment(uri) {
    var norm = String(uri)
        .toLowerCase()
        .replace(/%2e/g, '.')
        .replace(/%2f/g, '/')
        .replace(/%5c/g, '/')
        .replace(/\\/g, '/');
    var segs = norm.split('/');
    for (var i = 0; i < segs.length; i++) {
        if (segs[i] === '..') return true;
    }
    return false;
}

function resolvePath(p) {
    if (!p || p === '/') return '/index.html';
    if (p.charAt(0) !== '/') p = '/' + p;
    if (p.endsWith('/')) return p + 'index.html';
    var last = p.substring(p.lastIndexOf('/') + 1);
    if (last.indexOf('.') === -1) return p + '/index.html';
    return p;
}

function headerValue(headers, name) {
    var h = headers[name];
    return (h && h.value) ? String(h.value) : '';
}

// Length-checked, constant-time-ish string comparison (no early exit on first mismatch).
function secretEquals(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    var diff = 0;
    for (var i = 0; i < a.length; i++) {
        diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return diff === 0;
}

// True if X-Forwarded-Host may be used: the proxy secret matches, or none is configured yet.
async function forwardedHostTrusted(presented) {
    if (!kvsHandle) return false;
    var expected = '';
    try {
        expected = String(await kvsHandle.get(PROXY_SECRET_KEY) || '');
    } catch (e) {
        expected = '';  // key absent (get() throws) -> enforcement not enabled yet
    }
    if (!expected) return true;
    return secretEquals(presented, expected);
}

async function handler(event) {
    var request = event.request;
    var headers = request.headers || {};
    var uri = request.uri || '/';

    // 0. Path traversal guard (applies to every branch)
    if (hasDotDotSegment(uri)) {
        return notFound();
    }

    // 1. Backwards-compatible explicit /site/{tenant}/{site_id}/... path
    var siteMatch = uri.match(/^\/site\/([a-z0-9_-]+)\/([a-zA-Z0-9_-]+)(\/.*)?$/);
    if (siteMatch) {
        request.uri = '/' + siteMatch[1] + '/' + siteMatch[2] + '/published/current' + resolvePath(siteMatch[3] || '/');
        return request;
    }

    // 2. Effective hostname: X-Forwarded-Host (Cloudflare for SaaS Worker, if trusted) or Host
    var host = headerValue(headers, 'host').toLowerCase().split(':')[0];
    var fwdHost = headerValue(headers, 'x-forwarded-host').toLowerCase().split(',')[0].trim().split(':')[0];
    var presentedSecret = headerValue(headers, PROXY_SECRET_HEADER);
    if (headers[PROXY_SECRET_HEADER]) delete headers[PROXY_SECRET_HEADER];
    if (fwdHost && !(await forwardedHostTrusted(presentedSecret))) {
        fwdHost = '';
    }
    var effectiveHost = fwdHost || host;

    // 3. Resolve {tenant, site_id} via CloudFront KeyValueStore (get() throws on a missing key).
    //    "__"-prefixed keys are internal (e.g. preview secret) and never looked up.
    if (kvsHandle && effectiveHost && effectiveHost.indexOf('__') !== 0) {
        try {
            var raw = await kvsHandle.get(effectiveHost);
            if (raw) {
                var mapping = JSON.parse(raw);
                if (mapping && typeof mapping.tenant === 'string' && typeof mapping.site_id === 'string' &&
                        TENANT_RE.test(mapping.tenant) && SITE_RE.test(mapping.site_id)) {
                    request.uri = '/' + mapping.tenant + '/' + mapping.site_id + '/published/current' + resolvePath(uri);
                    return request;
                }
            }
        } catch (err) {}
    }

    // 4. Fail closed: never pass the original URI through to the bucket.
    return notFound();
}
