/**
 * CloudFront Function: Draft preview path rewrite (Task 1.118).
 *
 * Path: /preview or /preview/* with ?token=<jwt>
 * Validates JWT exp (no signature check at edge for MVP).
 * Rewrites to S3: {tenant}/{site_id}/draft/{path}
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var qs = request.querystring || {};

  if (!uri.startsWith("/preview")) {
    return request;
  }

  // Redirect /preview?token=X to /preview/?token=X so relative paths resolve correctly
  if (uri === "/preview") {
    var qsParts = [];
    for (var k in qs) {
      if (qs[k] && qs[k].value !== undefined) {
        qsParts.push(k + "=" + encodeURIComponent(qs[k].value));
      }
    }
    return {
      statusCode: 301,
      statusDescription: "Moved Permanently",
      headers: { location: { value: "/preview/" + (qsParts.length ? "?" + qsParts.join("&") : "") } },
    };
  }

  var token = qs.token && qs.token.value;
  if (!token) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Missing token" };
  }

  // JWT payload is base64url encoded (second part)
  var parts = token.split(".");
  if (parts.length < 2) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Invalid token" };
  }
  var payloadB64 = parts[1];

  // CF Functions cloudfront-js-2.0 runtime does not have Buffer.
  // Decode base64url manually: replace URL-safe chars, pad, then atob().
  var payloadJson;
  try {
    var b64 = payloadB64.replace(/-/g, "+").replace(/_/g, "/");
    var pad = b64.length % 4;
    if (pad === 2) b64 += "==";
    else if (pad === 3) b64 += "=";
    payloadJson = atob(b64);
  } catch (e) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Invalid token" };
  }

  var payload;
  try {
    payload = JSON.parse(payloadJson);
  } catch (e) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Invalid token" };
  }

  if (payload.type !== "draft") {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Invalid token" };
  }

  var now = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < now) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Token expired" };
  }

  var tenant = (payload.tenant_slug || "").toLowerCase();
  var siteId = payload.site_id || "";
  if (!tenant || !siteId) {
    return { statusCode: 403, statusDescription: "Forbidden", body: "Invalid token" };
  }

  // Strip /preview from path, get rest (e.g. "" or "blog/" or "posts/slug/")
  var rest = uri.length > 8 ? uri.substring(8) : "";
  if (rest.startsWith("/")) {
    rest = rest.substring(1);
  }
  if (!rest || rest.endsWith("/")) {
    rest = (rest || "") + "index.html";
  } else if (rest.indexOf(".") === -1) {
    // Extensionless path (e.g. "about") → "about/index.html"
    rest = rest + "/index.html";
  }

  request.uri = "/" + tenant + "/" + siteId + "/draft/" + rest;
  return request;
}
