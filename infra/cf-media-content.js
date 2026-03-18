/**
 * CloudFront Function: Media path rewrite (Task 1.110).
 *
 * /media/{tenant}/{site}/{filename} → S3 key {tenant}/{site}/{filename}
 * S3 layout: {tenant_slug}/{site_id}/{filename}
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (!uri.startsWith("/media/")) {
    return request;
  }

  var rest = uri.substring(7); // after "/media/"
  if (!rest || rest === "/") {
    return request;
  }

  request.uri = "/" + rest;
  return request;
}
