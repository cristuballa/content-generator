const fs = require('fs');
const { publishFacebookVideo } = require('./facebook_publisher');
const { publishInstagramReel } = require('./instagram_publisher');

async function main() {
  try {
    const rawArg = process.argv[2];
    if (!rawArg) {
      console.log(JSON.stringify({ success: false, error: 'No payload argument provided' }));
      process.exit(0);
    }

    let payload;
    try {
      const decoded = Buffer.from(rawArg, 'base64').toString('utf8');
      payload = JSON.parse(decoded);
    } catch (e) {
      console.log(JSON.stringify({ success: false, error: `Invalid base64/JSON payload: ${e.message}` }));
      process.exit(0);
    }

    const {
      filePath,
      title,
      facebookCaption,
      instagramCaption,
      targetPlatforms = ['facebook', 'instagram']
    } = payload;

    if (!filePath || !fs.existsSync(filePath)) {
      console.log(JSON.stringify({ success: false, error: `Video file not found at path: ${filePath}` }));
      process.exit(0);
    }

    console.error(`[publish_meta] Dispatching for: ${filePath}`);
    console.error(`[publish_meta] Target platforms:`, targetPlatforms);

    const results = {
      success: true,
      facebook_id: '',
      facebook_url: '',
      instagram_id: '',
      instagram_url: '',
      errors: {}
    };

    const tasks = [];

    // Facebook Task
    if (targetPlatforms.includes('facebook')) {
      tasks.push((async () => {
        try {
          console.error('[publish_meta] Starting Facebook upload...');
          const fbRes = await publishFacebookVideo(filePath, title, facebookCaption);
          results.facebook_id = fbRes.id;
          results.facebook_url = fbRes.url;
          console.error('[publish_meta] Facebook upload complete:', fbRes);
        } catch (err) {
          console.error('[publish_meta] Facebook upload error:', err);
          results.errors.facebook = err.message || String(err);
        }
      })());
    }

    // Instagram Task
    if (targetPlatforms.includes('instagram')) {
      tasks.push((async () => {
        try {
          console.error('[publish_meta] Starting Instagram upload...');
          const igRes = await publishInstagramReel(filePath, instagramCaption);
          results.instagram_id = igRes.id;
          results.instagram_url = igRes.url;
          console.error('[publish_meta] Instagram upload complete:', igRes);
        } catch (err) {
          console.error('[publish_meta] Instagram upload error:', err);
          results.errors.instagram = err.message || String(err);
        }
      })());
    }

    await Promise.all(tasks);

    // If all attempted platforms failed, mark success as false
    const attemptedCount = tasks.length;
    const failedCount = Object.keys(results.errors).length;
    if (attemptedCount > 0 && failedCount === attemptedCount) {
      results.success = false;
    }

    console.log(JSON.stringify(results));
  } catch (globalErr) {
    console.error('[publish_meta] Fatal error:', globalErr);
    console.log(JSON.stringify({
      success: false,
      error: globalErr.message || String(globalErr)
    }));
  }
}

main();
