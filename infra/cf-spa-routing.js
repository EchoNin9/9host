/**
 * CloudFront Function: SPA routing for admin frontend.
 *
 * Rewrites non-file paths to /index.html so React Router handles client-side
 * routing. Replaces distribution-level custom_error_response which interfered
 * with /site/* and /media/* behaviors returning real S3 errors.
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // If URI has a file extension (e.g. .js, .css, .png), pass through to S3
  var lastSlash = uri.lastIndexOf("/");
  if (uri.indexOf(".", lastSlash) > -1) {
    return request;
  }

  // All other paths → index.html (SPA client-side routing)
  request.uri = "/index.html";
  return request;
}
