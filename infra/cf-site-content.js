/**
 * CloudFront Function: Site content path rewrite (Task 1.97).
 *
 * Resolves Host header → tenant, path /site/{site_id}/* → S3 key
 * {tenant}/{site_id}/published/current/{rest}
 *
 * Example: acme.echo9.net/site/abc-123/index.html
 *   → S3 key: acme/abc-123/published/current/index.html
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var headers = request.headers;

  // Extract tenant from Host (e.g. acme.echo9.net → acme)
  var hostObj = headers.host || {};
  var host = (hostObj.value !== undefined && hostObj.value !== null) ? String(hostObj.value) : "";
  var tenant = "";
  var dot = host.indexOf(".");
  if (dot > 0) {
    tenant = host.substring(0, dot).toLowerCase();
  }
  if (!tenant) {
    return request;
  }

  // Path format: /site/{site_id}/... or /site/{site_id}
  if (!uri.startsWith("/site/")) {
    return request;
  }
  var rest = uri.substring(6); // after "/site/"
  var slash = rest.indexOf("/");
  var siteId;
  var pathPart;
  if (slash >= 0) {
    siteId = rest.substring(0, slash);
    pathPart = rest.substring(slash + 1);
  } else {
    siteId = rest;
    pathPart = "";
  }
  if (!siteId) {
    return request;
  }

  // Trailing slash or empty path → index.html
  if (!pathPart || pathPart.endsWith("/")) {
    pathPart = pathPart ? pathPart + "index.html" : "index.html";
  }

  // Rewrite to S3 path: {tenant}/{site_id}/published/current/{path}
  request.uri = "/" + tenant + "/" + siteId + "/published/current/" + pathPart;
  return request;
}
