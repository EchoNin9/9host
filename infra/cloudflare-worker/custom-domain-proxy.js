// 9host — Cloudflare for SaaS fallback origin Worker (SPEC §3 Module 1D, ADR-0001).
// Custom hostnames (CNAME -> proxy.echonin9.com) terminate TLS at Cloudflare and are
// forwarded to the public sites CloudFront distribution with X-Forwarded-Host, where
// cf-site-content.js resolves {tenant, site_id} from HostMappingKVS. X-9host-Proxy-Secret
// (Worker secret PROXY_SECRET) authenticates the forwarded host (T-18).
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const originHost = env.SITES_ORIGIN_HOST || "sites-origin.echo9.net";
    const targetUrl = `https://${originHost}${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.hostname);
    // T-18: proves to cf-site-content.js that X-Forwarded-Host came from this Worker. Must equal
    // the "__proxy_secret__" key in 9host-site-hosts-kvs (`wrangler secret put PROXY_SECRET`).
    // A client-supplied copy is never passed through.
    headers.delete("X-9host-Proxy-Secret");
    if (env.PROXY_SECRET) headers.set("X-9host-Proxy-Secret", env.PROXY_SECRET);
    return fetch(targetUrl, {
      method: request.method,
      headers,
      redirect: "manual",
    });
  },
};
