/**
 * CloudFront Function: Custom domain path resolution.
 *
 * Each custom domain has its own CloudFront distribution with the S3 origin
 * path pre-set to /{tenant}/{site_id}/published/current. This function:
 *   1. Strips legacy /site/{tenant}/{site_id}/ prefix from paths (published
 *      HTML contains hardcoded links with this prefix)
 *   2. Rewrites /media/{tenant}/{site_id}/ prefix to /media/ so the media
 *      cache behavior can route to the media S3 origin
 *   3. Resolves directories to index.html
 *   4. Redirects www to apex domain
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
  // Published HTML links use /site/{tenant}/{site_id}/about/ format.
  // On per-domain distributions the origin path already encodes tenant/site_id,
  // so we strip the prefix to get the clean path.
  if (uri.indexOf("/site/") === 0) {
    var rest = uri.substring(6); // after "/site/"
    // Filter empty segments from trailing slashes
    var segments = rest.split("/");
    var parts = [];
    for (var i = 0; i < segments.length; i++) {
      if (segments[i] !== "") parts.push(segments[i]);
    }
    // Need at least 2 non-empty segments (tenant + site_id) to strip
    if (parts.length >= 2) {
      var pathAfter = parts.slice(2).join("/");
      // Preserve trailing slash from original URI
      if (rest.charAt(rest.length - 1) === "/" && pathAfter && pathAfter.charAt(pathAfter.length - 1) !== "/") {
        pathAfter = pathAfter + "/";
      }
      uri = "/" + pathAfter;
      if (uri === "//" || uri === "") {
        uri = "/";
      }
    }
  }

  // /media/* paths are handled by the /media/* cache behavior + cf-media-content.js.
  // That function already strips /media/ prefix correctly. Just pass through.
  if (uri.indexOf("/media/") === 0) {
    request.uri = uri;
    return request;
  }

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
