/**
 * CloudFront Function: Custom domain path resolution.
 *
 * Each custom domain has its own CloudFront distribution with the S3 origin
 * path pre-set to /{tenant}/{site_id}/published/current. This function only
 * resolves paths (directories → index.html) and redirects www → apex.
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
  }

  return request;
}
