/**
 * CloudFront Function: Site content path rewrite (Task 1.97, 1.108).
 *
 * Path formats:
 *   /site/{site_id}/*     — tenant from Host (e.g. acme.echo9.net)
 *   /site/{tenant}/{site_id}/* — tenant from path (site-slug subdomains)
 *
 * S3 key: {tenant}/{site_id}/published/current/{rest}
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var headers = request.headers;

  // Extract tenant from Host (e.g. acme.echo9.net → acme)
  var hostObj = headers.host || {};
  var host = (hostObj.value !== undefined && hostObj.value !== null) ? String(hostObj.value) : "";
  var tenantFromHost = "";
  var dot = host.indexOf(".");
  if (dot > 0) {
    tenantFromHost = host.substring(0, dot).toLowerCase();
  }

  if (!uri.startsWith("/site/")) {
    return request;
  }
  var rest = uri.substring(6); // after "/site/"
  var parts = rest.split("/").filter(Boolean);
  var tenant = tenantFromHost;
  var siteId;
  var pathPart;

  // /site/{tenant}/{site_id}/... — tenant in path (Task 1.108)
  if (parts.length >= 2) {
    tenant = parts[0].toLowerCase();
    siteId = parts[1];
    pathPart = parts.slice(2).join("/");
  } else if (parts.length === 1) {
    siteId = parts[0];
    pathPart = "";
  } else {
    return request;
  }

  if (!siteId || !tenant) {
    return request;
  }

  // Trailing slash or empty path → index.html
  if (!pathPart || pathPart.endsWith("/")) {
    pathPart = pathPart ? pathPart + "index.html" : "index.html";
  }

  request.uri = "/" + tenant + "/" + siteId + "/published/current/" + pathPart;
  return request;
}
