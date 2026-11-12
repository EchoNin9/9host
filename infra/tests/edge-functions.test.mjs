// Regression tests for the CloudFront Functions. Run: node --test infra/tests/
// (Node 26 rejects a bare directory argument; use `node --test infra/tests/*.test.mjs` there.)
// No dependencies: each function's source is loaded with its `import` lines removed and
// `cf` / `crypto` stubbed (cloudfront-js-2.0 modules are not available under node).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

// kvs: object of key -> string, or a function (key) => string | throws.
function load(file, kvs) {
  const src = readFileSync(join(here, '..', file), 'utf8')
    .replace(/^import cf from 'cloudfront';\s*$/m, '')
    .replace(/^import crypto from 'crypto';\s*$/m, '');
  assert.ok(!/^import /m.test(src), `${file}: unexpected import left in source`);
  const get = async (key) => {
    if (typeof kvs === 'function') return kvs(key);
    if (!(key in kvs)) throw new Error('KeyNotFound');
    return kvs[key];
  };
  const cf = { kvs: () => ({ get }) };
  return new Function('cf', 'crypto', `${src}\nreturn handler;`)(cf, { createHmac });
}

const req = (uri, host, extra = {}) => ({
  request: { uri, headers: host ? { host: { value: host }, ...extra } : { ...extra }, querystring: {} },
});

// ---------------------------------------------------------------- cf-site-content.js
const MAPPING = { 'band.echo9.net': JSON.stringify({ tenant: 'acme', site_id: 's1' }) };
const site = (kvs = MAPPING) => load('cf-site-content.js', kvs);
const BASE = '/acme/s1/published/current';

test('site: mapped host rewrites', async () => {
  const h = site();
  const cases = [['/', '/index.html'], ['/blog/', '/blog/index.html'], ['/blog', '/blog/index.html'],
    ['/style.css', '/style.css']];
  for (const [uri, want] of cases) {
    const out = await h(req(uri, 'band.echo9.net'));
    assert.equal(out.uri, BASE + want, uri);
  }
});

test('site: X-Forwarded-Host takes precedence', async () => {
  const out = await site({ 'myband.com': MAPPING['band.echo9.net'] })(
    req('/', 'proxy.echo9.net', { 'x-forwarded-host': { value: 'myband.com' } }));
  assert.equal(out.uri, BASE + '/index.html');
});

test('site: unmapped host -> 404', async () => {
  const out = await site()(req('/', 'nobody.echo9.net'));
  assert.equal(out.statusCode, 404);
});

test('site: KVS throwing -> 404', async () => {
  const out = await site(() => { throw new Error('boom'); })(req('/', 'band.echo9.net'));
  assert.equal(out.statusCode, 404);
});

test('site: draft path on an unmapped host -> 404 (never passed through)', async () => {
  const out = await site()(req('/acme/s1/draft/index.html', 'nobody.echo9.net'));
  assert.equal(out.statusCode, 404);
});

test('site: legacy /site/{t}/{s}/ rewrite', async () => {
  const h = site({});
  assert.equal((await h(req('/site/acme/s1/', 'x.echo9.net'))).uri, BASE + '/index.html');
  assert.equal((await h(req('/site/acme/s1/blog/post', 'x.echo9.net'))).uri, BASE + '/blog/post/index.html');
});

test('site: ".." and "%2e%2e" segments -> 404', async () => {
  const h = site();
  for (const uri of ['/../draft/index.html', '/a/%2e%2e/b', '/a/%2E%2e/b', '/a/..%2fb', '/a/..\\b',
    '/site/acme/s1/../../x/y']) {
    assert.equal((await h(req(uri, 'band.echo9.net'))).statusCode, 404, uri);
  }
});

// T-18: X-Forwarded-Host is only trusted with the Worker's shared secret once configured.
const SECRET = 'proxy-shared-secret-123';
const SECRET_KVS = { ...MAPPING, 'myband.com': MAPPING['band.echo9.net'], __proxy_secret__: SECRET };
const fwd = (host, secret) => ({
  'x-forwarded-host': { value: host },
  ...(secret === undefined ? {} : { 'x-9host-proxy-secret': { value: secret } }),
});

test('site: X-Forwarded-Host with the correct proxy secret is honoured', async () => {
  const ev = req('/', 'sites-origin.echo9.net', fwd('myband.com', SECRET));
  const out = await site(SECRET_KVS)(ev);
  assert.equal(out.uri, BASE + '/index.html');
  assert.ok(!('x-9host-proxy-secret' in out.headers), 'secret header stripped');
});

test('site: X-Forwarded-Host without / with a wrong proxy secret is ignored (Host used)', async () => {
  const h = site(SECRET_KVS);
  for (const secret of [undefined, '', 'wrong', SECRET + 'x', SECRET.slice(0, -1)]) {
    // Spoofing another site's hostname via a public site host -> served as the Host's own site.
    const viaPublic = await h(req('/', 'band.echo9.net', fwd('other.example', secret)));
    assert.equal(viaPublic.uri, BASE + '/index.html', String(secret));
    // Via the bare origin host (unmapped) -> 404, never the forwarded site.
    const viaOrigin = await h(req('/', 'sites-origin.echo9.net', fwd('myband.com', secret)));
    assert.equal(viaOrigin.statusCode, 404, String(secret));
  }
});

test('site: proxy secret is not readable as a hostname mapping', async () => {
  const out = await site(SECRET_KVS)(req('/', '__proxy_secret__', fwd('__proxy_secret__', SECRET)));
  assert.equal(out.statusCode, 404);
});

test('site: no __proxy_secret__ in KVS (rollout) -> X-Forwarded-Host trusted as before', async () => {
  const kvs = { 'myband.com': MAPPING['band.echo9.net'] };
  const out = await site(kvs)(req('/', 'sites-origin.echo9.net', fwd('myband.com', 'anything')));
  assert.equal(out.uri, BASE + '/index.html');
});

test('site: __proxy_secret__ read failing (not just absent) -> X-Forwarded-Host trusted as before', async () => {
  const kvs = (key) => {
    if (key === '__proxy_secret__') throw new Error('KVS unavailable');
    if (key === 'myband.com') return MAPPING['band.echo9.net'];
    throw new Error('KeyNotFound');
  };
  const out = await site(kvs)(req('/', 'sites-origin.echo9.net', fwd('myband.com')));
  assert.equal(out.uri, BASE + '/index.html');
});

// T-21: cloudfront-js-2.0 fails to load a function with `await` inside call arguments or other
// compound expressions ("SyntaxError: await in arguments not supported"), which 503s every
// request although node runs it fine. Only allow `[var] x = await <expr>;` statements.
test('cloudfront functions: await only as a plain assignment (runtime restriction)', () => {
  for (const file of ['cf-site-content.js', 'cf-preview-content.js', 'cf-media-content.js', 'cf-spa-routing.js']) {
    const lines = readFileSync(join(here, '..', file), 'utf8').split('\n');
    lines.forEach((line, i) => {
      const code = line.replace(/\/\/.*$/, '');
      if (!/\bawait\b/.test(code)) return;
      assert.match(code, /^\s*(var\s+)?[\w$.]+\s*=\s*await\s+[\w$.]+\([^()]*\);\s*$/, `${file}:${i + 1}: ${line.trim()}`);
    });
  }
});

// ---------------------------------------------------- cloudflare-worker/custom-domain-proxy.js
function loadWorker() {
  const src = readFileSync(join(here, '..', 'cloudflare-worker', 'custom-domain-proxy.js'), 'utf8')
    .replace(/^export default /m, 'return ');
  const sent = [];
  const fakeFetch = async (url, init) => { sent.push({ url, headers: init.headers, method: init.method }); return 'ok'; };
  return { worker: new Function('fetch', src)(fakeFetch), sent };
}

test('worker: forwards host, sends the proxy secret and drops a client-supplied one', async () => {
  const { worker, sent } = loadWorker();
  const request = new Request('https://myband.com/blog/?a=1', {
    headers: { 'X-9host-Proxy-Secret': 'attacker', 'X-Forwarded-Host': 'evil.example' },
  });
  await worker.fetch(request, { SITES_ORIGIN_HOST: 'sites-origin.echo9.net', PROXY_SECRET: SECRET });
  assert.equal(sent[0].url, 'https://sites-origin.echo9.net/blog/?a=1');
  assert.equal(sent[0].headers.get('x-forwarded-host'), 'myband.com');
  assert.equal(sent[0].headers.get('x-9host-proxy-secret'), SECRET);

  await worker.fetch(request, {});  // secret not configured: header absent, never the client's
  assert.equal(sent[1].headers.get('x-9host-proxy-secret'), null);
});

// -------------------------------------------------------------- cf-preview-content.js
const RAW_SECRET = 'raw-tuser-signing-secret';
const DERIVED = createHash('sha256').update(`${RAW_SECRET}:9host-preview-v1`).digest('hex');
const b64u = (o) => Buffer.from(typeof o === 'string' ? o : JSON.stringify(o)).toString('base64url');

function token(key, claims = {}, header = { alg: 'HS256', typ: 'JWT' }) {
  const now = Math.floor(Date.now() / 1000);
  const body = { tenant_slug: 'acme', site_id: 's1', type: 'draft', iat: now, exp: now + 3600, ...claims };
  const signing = `${b64u(header)}.${b64u(body)}`;
  return `${signing}.${createHmac('sha256', key).update(signing).digest('base64url')}`;
}

const preview = (kvs = { __preview_jwt_secret__: DERIVED }) => load('cf-preview-content.js', kvs);
const previewReq = (uri, tok) => ({ request: { uri, headers: {}, querystring: tok ? { token: { value: tok } } : {} } });

test('preview: valid token served and rewritten to draft/', async () => {
  const h = preview();
  const t = token(DERIVED);
  assert.equal((await h(previewReq('/preview/', t))).uri, '/acme/s1/draft/index.html');
  assert.equal((await h(previewReq('/preview/blog/', t))).uri, '/acme/s1/draft/blog/index.html');
  assert.equal((await h(previewReq('/preview/style.css', t))).uri, '/acme/s1/draft/style.css');
});

test('preview: bad signature -> 403', async () => {
  const t = token(DERIVED);
  const bad = t.slice(0, -2) + (t.endsWith('AA') ? 'BB' : 'AA');
  assert.equal((await preview()(previewReq('/preview/', bad))).statusCode, 403);
  assert.equal((await preview()(previewReq('/preview/', token('some-other-key')))).statusCode, 403);
});

test('preview: expired -> 403', async () => {
  const t = token(DERIVED, { exp: Math.floor(Date.now() / 1000) - 10 });
  assert.equal((await preview()(previewReq('/preview/', t))).statusCode, 403);
});

test('preview: missing secret in KVS (or KVS failing) -> 403', async () => {
  const t = token(DERIVED);
  assert.equal((await preview({})(previewReq('/preview/', t))).statusCode, 403);
  assert.equal((await preview(() => { throw new Error('boom'); })(previewReq('/preview/', t))).statusCode, 403);
});

test('preview: missing token, alg none, wrong type -> 403', async () => {
  const h = preview();
  assert.equal((await h(previewReq('/preview/', null))).statusCode, 403);
  assert.equal((await h(previewReq('/preview/', token(DERIVED, {}, { alg: 'none' })))).statusCode, 403);
  assert.equal((await h(previewReq('/preview/', token(DERIVED, { type: 'access' })))).statusCode, 403);
});

test('preview: ".." in path rejected even with a valid token', async () => {
  const h = preview();
  const t = token(DERIVED);
  for (const uri of ['/preview/../x/y', '/preview/a/%2e%2e/b', '/preview/%2E%2E/b', '/preview/a/..%2fb']) {
    assert.equal((await h(previewReq(uri, t))).statusCode, 403, uri);
  }
});

test('preview: token signed with the raw (non-derived) secret -> 403', async () => {
  const t = token(RAW_SECRET);
  assert.equal((await preview()(previewReq('/preview/', t))).statusCode, 403);
});
