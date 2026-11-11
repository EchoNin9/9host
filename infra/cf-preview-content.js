/**
 * CloudFront Function (cloudfront-js-2.0): Draft preview (Task 1.118; SPEC Bug #8 fix).
 *
 * Path: /preview or /preview/* with ?token=<HS256 JWT issued by api/draft_handler.py>
 * Verifies the JWT HMAC-SHA256 signature against the key stored in KVS
 * (9host-site-hosts-kvs, key "__preview_jwt_secret__": hex sha256 of
 * "<jwt secret>:9host-preview-v1", used as the raw UTF-8 key string; matches
 * api/draft_handler.py) and checks exp BEFORE
 * serving any draft/ content. Rejects with 403 on a missing/invalid/expired token
 * or when the secret is unavailable (fail closed).
 * Rewrites to S3: {tenant}/{site_id}/draft/{path}
 *
 * The CloudFront Functions runtime has no WebCrypto (crypto.subtle); the built-in
 * 'crypto' module's createHmac + a constant-time comparison is used instead.
 */
import cf from 'cloudfront';
import crypto from 'crypto';

var PREVIEW_SECRET_KEY = '__preview_jwt_secret__';

var kvsHandle = null;
try {
    kvsHandle = cf.kvs();
} catch (e) {}

function forbidden(msg) {
    return { statusCode: 403, statusDescription: 'Forbidden', body: msg };
}

function b64urlDecode(s) {
    var b64 = s.replace(/-/g, '+').replace(/_/g, '/');
    var pad = b64.length % 4;
    if (pad === 2) b64 += '==';
    else if (pad === 3) b64 += '=';
    else if (pad === 1) throw new Error('bad base64url');
    // Buffer is documented in cloudfront-js-2.0 (atob is not); decode as UTF-8 JSON text.
    return Buffer.from(b64, 'base64').toString('utf8');
}

// True if any path segment is "..", after normalising %2e / %2f / %5c / backslash.
// (Duplicated from cf-site-content.js: CloudFront Functions cannot import each other.)
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

// Constant-time string comparison (length is not secret: HS256 sig is always 43 chars).
function safeEqual(a, b) {
    if (a.length !== b.length) return false;
    var diff = 0;
    for (var i = 0; i < a.length; i++) {
        diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return diff === 0;
}

async function handler(event) {
    var request = event.request;
    var uri = request.uri;
    var qs = request.querystring || {};

    if (!uri.startsWith('/preview')) {
        return request;
    }

    if (hasDotDotSegment(uri)) {
        return forbidden('Forbidden');
    }

    // Redirect /preview?token=X to /preview/?token=X so relative paths resolve correctly
    if (uri === '/preview') {
        var qsParts = [];
        for (var k in qs) {
            if (qs[k] && qs[k].value !== undefined) {
                qsParts.push(k + '=' + encodeURIComponent(qs[k].value));
            }
        }
        return {
            statusCode: 301,
            statusDescription: 'Moved Permanently',
            headers: { location: { value: '/preview/' + (qsParts.length ? '?' + qsParts.join('&') : '') } },
        };
    }

    var token = qs.token && qs.token.value;
    if (!token) {
        return forbidden('Missing token');
    }

    var parts = token.split('.');
    if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
        return forbidden('Invalid token');
    }

    // 1. Header must declare HS256 (no alg confusion / "none")
    var header;
    var payload;
    try {
        header = JSON.parse(b64urlDecode(parts[0]));
        payload = JSON.parse(b64urlDecode(parts[1]));
    } catch (e) {
        return forbidden('Invalid token');
    }
    if (!header || header.alg !== 'HS256' || !payload) {
        return forbidden('Invalid token');
    }

    // 2. Verify signature with the secret from KVS (fail closed)
    var secret = null;
    if (kvsHandle) {
        try {
            secret = await kvsHandle.get(PREVIEW_SECRET_KEY);
        } catch (e) {
            secret = null;
        }
    }
    if (!secret) {
        return forbidden('Preview unavailable');
    }
    var expected = crypto.createHmac('sha256', secret).update(parts[0] + '.' + parts[1]).digest('base64url');
    if (!safeEqual(expected, parts[2])) {
        return forbidden('Invalid token');
    }

    // 3. Claims: type, exp (required), tenant/site
    if (payload.type !== 'draft') {
        return forbidden('Invalid token');
    }
    var now = Math.floor(Date.now() / 1000);
    if (typeof payload.exp !== 'number' || payload.exp < now) {
        return forbidden('Token expired');
    }

    var tenant = String(payload.tenant_slug || '').toLowerCase();
    var siteId = String(payload.site_id || '');
    if (!/^[a-z0-9_-]+$/.test(tenant) || !/^[a-zA-Z0-9_-]+$/.test(siteId)) {
        return forbidden('Invalid token');
    }

    // Strip /preview from path, get rest (e.g. "" or "blog/" or "posts/slug/")
    var rest = uri.length > 8 ? uri.substring(8) : '';
    if (rest.startsWith('/')) {
        rest = rest.substring(1);
    }
    if (!rest || rest.endsWith('/')) {
        rest = (rest || '') + 'index.html';
    } else if (rest.substring(rest.lastIndexOf('/') + 1).indexOf('.') === -1) {
        // Extensionless path (e.g. "about") → "about/index.html"
        rest = rest + '/index.html';
    }

    request.uri = '/' + tenant + '/' + siteId + '/draft/' + rest;
    return request;
}
