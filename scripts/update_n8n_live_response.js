const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT id, name, active, nodes, connections, versionCounter FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  let nodes = JSON.parse(row.nodes);

  // 1. Bulletproof Dry Run Log & Respond
  const dryRunNode = nodes.find(n => n.name === 'Dry Run Log & Respond');
  if (dryRunNode) {
    dryRunNode.parameters = {
      respondWith: 'json',
      responseBody: `={{
  (() => {
    const b = $json && $json.body ? $json.body : {};
    return JSON.stringify({
      success: true,
      mode: "dry_run",
      message: "Simulated dispatch received successfully by n8n.",
      video: (b.video && b.video.filename) || "",
      platforms: b.target_platforms || [],
      received_at: new Date().toISOString()
    });
  })()
}}`,
      options: {
        responseCode: 200
      }
    };
  }

  // 2. Bulletproof Live Dispatch Response
  const liveNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (liveNode) {
    liveNode.parameters = {
      respondWith: 'json',
      responseBody: `={{
  (() => {
    let ytId = '';
    try {
      const ytNode = $('YouTube Video Upload');
      if (ytNode) {
        const item = ytNode.first();
        ytId = (item && item.json && (item.json.uploadId || item.json.id)) || '';
      }
    } catch (e) {}

    let videoName = '';
    let platforms = [];
    try {
      const trigger = $('KCT Webhook Trigger');
      if (trigger) {
        const item = trigger.first();
        videoName = (item && item.json && item.json.body && item.json.body.video && item.json.body.video.filename) || '';
        platforms = (item && item.json && item.json.body && item.json.body.target_platforms) || [];
      }
    } catch (e) {}

    return JSON.stringify({
      success: true,
      message: "Video successfully processed by n8n.",
      video: videoName,
      youtube_id: ytId,
      youtube_url: ytId ? 'https://youtu.be/' + ytId : '',
      target_platforms: platforms
    });
  })()
}}`,
      options: {
        responseCode: 200
      }
    };
  }

  const updatedNodesStr = JSON.stringify(nodes);
  const newCounter = (row.versionCounter || 1) + 1;

  db.serialize(() => {
    db.run(
      'UPDATE workflow_entity SET nodes = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
      [updatedNodesStr, newCounter, WORKFLOW_ID],
      function(updateErr) {
        if (updateErr) {
          console.error('Error updating workflow_entity:', updateErr);
          process.exit(1);
        }
        console.log('Successfully updated Dry Run & Live Response in workflow_entity!');
      }
    );

    db.run(
      'UPDATE workflow_history SET nodes = ? WHERE workflowId = ?',
      [updatedNodesStr, WORKFLOW_ID],
      function(histErr) {
        if (histErr) {
          console.error('Error updating workflow_history:', histErr);
          process.exit(1);
        }
        console.log('Successfully updated workflow_history!');
        db.close();
      }
    );
  });
});
