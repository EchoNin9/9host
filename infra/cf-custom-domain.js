/**
 * CloudFront Function: Custom domain path resolution.
 *
 * Each custom domain has its own CloudFront distribution with the S3 origin
 * path pre-set to /{tenant}/{site_id}/published/current. This function:
 *   1. Strips legacy /site/{tenant}/{site_id}/ prefix from paths (published
 *      HTML may contain hardcoded links with this prefix)
 *   2. Resolves directories → index.html
 *   3. Redirects www → apex
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Redirect www.domain.com → domain.com (301)
  var hostObj = request.headers.host || {};
  var host = (hostObj.value !== undefined && hostObj.value !== null)
    ? String(hostObj.value).toLowerCase().split(":")[0]
    : "";

  if (host.indexOf("www.") === 0) {
    return {
      statusCode: 301,
      statusDescription: "Moved Permanently",
      headers: {
        location: { value: "https://" + host.substring(4) + uri }
      }
    };
  }

  // Strip legacy /site/{tenant}/{site_id}/ prefix.
  // Published HTML links use /site/{tenant}/{site_id}/about/ format,
  // but on custom domain distributions the origin path already encodes
  // the tenant and site_id, so we strip the prefix to get the clean path.
  if (uri.indexOf("/site/") === 0) {
    var rest = uri.substring(6); // after "/site/"
    var parts = rest.split("/");
    // /site/{tenant}/{site_id}/... → extract path after tenant + site_id
    if (parts.length >= 2) {
      // parts[0]=tenant, parts[1]=site_id, parts[2..]=path
      uri = "/" + parts.slice(2).join("/");
      if (uri === "/") {
        uri = "/";
      }
    }
  }

  // Also strip /media/{tenant}/{site_id}/ → rewrite to /media/{tenant}/{site_id}/
  // (media links need to go to the sites distribution, not this one — leave as-is
  // so they hit a 403 and the user sees the correct media URL)

  // Resolve: root → index.html
  if (uri === "/" || uri === "") {
    request.uri = "/index.html";
    return request;
  }

  // Trailing slash → directory index
  if (uri.charAt(uri.length - 1) === "/") {
    request.uri = uri + "index.html";
    return request;
  }

  // No file extension after last slash → treat as directory
  var lastSlash = uri.lastIndexOf("/");
  var afterSlash = uri.substring(lastSlash + 1);
  if (afterSlash.indexOf(".") === -1) {
    request.uri = uri + "/index.html";
  } else {
    request.uri = uri;
  }

  return request;
}
