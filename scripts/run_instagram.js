const fs = require('fs');
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

    const { filePath, caption } = payload;
    if (!filePath || !fs.existsSync(filePath)) {
      console.log(JSON.stringify({ success: false, error: `Video file not found at path: ${filePath}` }));
      process.exit(0);
    }

    console.error(`[run_instagram] Starting Instagram publishing for: ${filePath}`);
    const result = await publishInstagramReel(filePath, caption || '');
    console.error(`[run_instagram] Published successfully:`, result);

    console.log(JSON.stringify({
      success: true,
      instagram_id: result.id,
      instagram_url: result.url
    }));
  } catch (err) {
    console.error(`[run_instagram] Error:`, err);
    console.log(JSON.stringify({
      success: false,
      error: err.message || String(err)
    }));
  }
}

main();
