// 9host — Cloudflare for SaaS fallback origin Worker (SPEC §3 Module 1D, ADR-0001).
// Custom hostnames (CNAME -> proxy.echonin9.com) terminate TLS at Cloudflare and are
// forwarded to the public sites CloudFront distribution with X-Forwarded-Host, where
// cf-site-content.js resolves {tenant, site_id} from HostMappingKVS.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const originHost = env.SITES_ORIGIN_HOST || "sites-origin.echo9.net";
    const targetUrl = `https://${originHost}${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.hostname);
    return fetch(targetUrl, {
      method: request.method,
      headers,
      redirect: "manual",
    });
  },
};
