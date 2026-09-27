const { openAsBlob } = require('fs');
const path = require('path');

const PAGE_ID = '1095048317029830';
const TOKEN = 'EAAPLBqWnsIUBSlFk9W3RMjlFVQZBYTT7wtsKXwGhGE9SNpRwGlGs3VqKlMsHF8XK6o7WSNF7P3UqDltbOPsiFNFHQwgQ6U9N4m0pOM0SzOJQh48upbZAMCPBgpK6L0qFlbCoPC2S7VTd84fOIRmnTQIhWMRkm5ZBhGTgsaWW5B5ZBVq5bxaIsEQl9O4Kh3lucX5a';

async function publishFacebookVideo(filePath, title, description) {
  console.log(`[FB] Publishing video ${filePath} to Facebook Page ${PAGE_ID}...`);
  const blob = await openAsBlob(filePath);
  const filename = path.basename(filePath);

  const form = new FormData();
  form.append('source', blob, filename);
  form.append('title', title || '');
  form.append('description', description || '');
  form.append('published', 'true');

  const url = `https://graph-video.facebook.com/v20.0/${PAGE_ID}/videos`;
  console.log(`[FB] Sending POST request to ${url}...`);

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${TOKEN}`
    },
    body: form
  });

  const data = await response.json();
  console.log(`[FB] Response:`, data);

  if (!response.ok || !data.id) {
    throw new Error(`Facebook upload failed (${response.status}): ${JSON.stringify(data)}`);
  }

  const videoId = data.id;
  const videoUrl = `https://www.facebook.com/watch/?v=${videoId}`;

  return {
    success: true,
    id: videoId,
    url: videoUrl
  };
}

module.exports = { publishFacebookVideo };
