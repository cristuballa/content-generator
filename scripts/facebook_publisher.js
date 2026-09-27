const { openAsBlob } = require('fs');
const path = require('path');

const PAGE_ID = '1095048317029830';
const TOKEN = process.env.META_PAGE_ACCESS_TOKEN || 'EAAPLBqWnsIUBSgIZALnrrsYQyl247OjpB8yuAkZAFqiMqqJdhfQ7IwxtX5rK6QLDXxewhnzex0glFzLoNftr1uo5tEVmyFOWoteZBOZCrg1vPcmldoZBDqFKwXSxGKKbcGzZBnzgv4sXXaVtKs1a6ZAZAMryXwyDWU6ug8WWzzVBXZAmqgHDomEXqnZBQUAeFuzyOrAFqZB';

async function publishFacebookVideo(filePath, title, description, scheduledPublishTime = null) {
  console.log(`[FB] Publishing video ${filePath} to Facebook Page ${PAGE_ID}...`);
  const blob = await openAsBlob(filePath);
  const filename = path.basename(filePath);

  const form = new FormData();
  form.append('source', blob, filename);
  form.append('title', title || '');
  form.append('description', description || '');

  const nowSec = Math.floor(Date.now() / 1000);
  const schedTime = Number(scheduledPublishTime);
  // Facebook requires scheduled_publish_time to be between 10 minutes (600s) and 75 days in the future
  if (schedTime && schedTime > (nowSec + 600)) {
    console.log(`[FB] Setting native scheduled publish time: ${schedTime} (in ${Math.round((schedTime - nowSec) / 60)} minutes)`);
    form.append('published', 'false');
    form.append('scheduled_publish_time', String(schedTime));
  } else {
    form.append('published', 'true');
  }

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
