const fs = require('fs');
const https = require('https');
const { URL } = require('url');

const TOKEN = 'EAAPLBqWnsIUBSlFk9W3RMjlFVQZBYTT7wtsKXwGhGE9SNpRwGlGs3VqKlMsHF8XK6o7WSNF7P3UqDltbOPsiFNFHQwgQ6U9N4m0pOM0SzOJQh48upbZAMCPBgpK6L0qFlbCoPC2S7VTd84fOIRmnTQIhWMRkm5ZBhGTgsaWW5B5ZBVq5bxaIsEQl9O4Kh3lucX5a';
const IG_USER_ID = '17841429371050878';

function httpRequest(urlStr, options = {}, bodyData = null) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(urlStr);
    const reqOptions = {
      hostname: parsed.hostname,
      port: parsed.port || 443,
      path: parsed.pathname + parsed.search,
      method: options.method || 'GET',
      headers: options.headers || {}
    };

    const req = https.request(reqOptions, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve({ statusCode: res.statusCode, headers: res.headers, data: json });
        } catch (e) {
          resolve({ statusCode: res.statusCode, headers: res.headers, raw: data });
        }
      });
    });

    req.on('error', reject);

    if (bodyData) {
      if (Buffer.isBuffer(bodyData)) {
        req.write(bodyData);
      } else if (typeof bodyData === 'string') {
        req.write(bodyData);
      }
    }
    req.end();
  });
}

function uploadBinaryStream(urlStr, filePath, token) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(urlStr);
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;

    const reqOptions = {
      hostname: parsed.hostname,
      port: parsed.port || 443,
      path: parsed.pathname + parsed.search,
      method: 'POST',
      headers: {
        'Authorization': `OAuth ${token}`,
        'offset': '0',
        'file_size': String(fileSize),
        'Content-Type': 'application/octet-stream',
        'Content-Length': fileSize
      }
    };

    const req = https.request(reqOptions, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve({ statusCode: res.statusCode, data: json });
        } catch (e) {
          resolve({ statusCode: res.statusCode, raw: data });
        }
      });
    });

    req.on('error', reject);

    const fileStream = fs.createReadStream(filePath);
    fileStream.pipe(req);
  });
}

async function publishInstagramReel(filePath, caption) {
  console.log(`[IG] Step 1: Initializing Reel container for ${filePath}...`);
  const initParams = new URLSearchParams({
    media_type: 'REELS',
    upload_type: 'resumable',
    caption: caption,
    access_token: TOKEN
  });

  const initRes = await httpRequest(`https://graph.facebook.com/v20.0/${IG_USER_ID}/media`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }, initParams.toString());

  console.log('[IG] Init response:', initRes);
  if (!initRes.data || !initRes.data.id || !initRes.data.uri) {
    throw new Error(`Failed to create IG container: ${JSON.stringify(initRes)}`);
  }

  const containerId = initRes.data.id;
  const uploadUri = initRes.data.uri;

  console.log(`[IG] Step 2: Uploading video binary (${fs.statSync(filePath).size} bytes) to ${uploadUri}...`);
  const uploadRes = await uploadBinaryStream(uploadUri, filePath, TOKEN);
  console.log('[IG] Upload response:', uploadRes);

  console.log(`[IG] Step 3: Polling container status for container ${containerId}...`);
  let isReady = false;
  let attempts = 0;
  const maxAttempts = 30; // up to 150 seconds

  while (!isReady && attempts < maxAttempts) {
    attempts++;
    await new Promise(r => setTimeout(r, 5000));

    const statusRes = await httpRequest(`https://graph.facebook.com/v20.0/${containerId}?fields=status_code,status&access_token=${TOKEN}`);
    console.log(`[IG] Attempt ${attempts}/${maxAttempts} status:`, statusRes.data);

    const code = statusRes.data && statusRes.data.status_code;
    if (code === 'FINISHED') {
      isReady = true;
      break;
    } else if (code === 'ERROR' || code === 'EXPIRED') {
      throw new Error(`IG container processing failed with status: ${code} - ${JSON.stringify(statusRes.data)}`);
    }
  }

  if (!isReady) {
    throw new Error('IG container processing timed out after 150 seconds.');
  }

  console.log(`[IG] Step 4: Publishing Reel...`);
  const publishParams = new URLSearchParams({
    creation_id: containerId,
    access_token: TOKEN
  });

  const pubRes = await httpRequest(`https://graph.facebook.com/v20.0/${IG_USER_ID}/media_publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }, publishParams.toString());

  console.log('[IG] Publish response:', pubRes);
  if (!pubRes.data || !pubRes.data.id) {
    throw new Error(`Failed to publish IG Reel: ${JSON.stringify(pubRes)}`);
  }

  const mediaId = pubRes.data.id;

  // Get permalink
  let permalink = `https://www.instagram.com/reel/${mediaId}/`;
  try {
    const mediaInfo = await httpRequest(`https://graph.facebook.com/v20.0/${mediaId}?fields=permalink&access_token=${TOKEN}`);
    if (mediaInfo.data && mediaInfo.data.permalink) {
      permalink = mediaInfo.data.permalink;
    }
  } catch (e) {}

  return {
    success: true,
    id: mediaId,
    url: permalink
  };
}

module.exports = { publishInstagramReel };
