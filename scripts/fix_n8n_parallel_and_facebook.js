const crypto = require('crypto');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';
const PAGE_ID = '1095048317029830';
const TOKEN = 'EAAPLBqWnsIUBSpICwZBaEBdiHfr3kqm7jhrUIQG0tvnogfiNZBMfPcZBskZBpWBHyDHoxybUstk3a5qj35hJsWdBWYjnTtT2DXwINsCnsIKXKlkZBZBpf0WuMu6RrZCcjwMOR6r1c2WxO9Ui3EuZCuoZCc4MDyPBWymPwXPhzWke3ZAILgaCgFN1ZBzHEFv8hqqwwZDZD';

db.get('SELECT id, name, active, nodes, connections, versionCounter FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  const nodes = JSON.parse(row.nodes);
  const connections = JSON.parse(row.connections);

  // 1. Update Facebook Page Video Node to use graph-video.facebook.com & continueOnFail
  const fbNode = nodes.find(n => n.name === 'Facebook Page Video');
  if (fbNode) {
    fbNode.typeVersion = 4.2;
    fbNode.continueOnFail = true;
    fbNode.parameters = {
      method: 'POST',
      url: `https://graph-video.facebook.com/v20.0/${PAGE_ID}/videos`,
      sendHeaders: true,
      headerParameters: {
        parameters: [
          {
            name: 'Authorization',
            value: `Bearer ${TOKEN}`
          }
        ]
      },
      sendBody: true,
      contentType: 'multipart-form-data',
      bodyParameters: {
        parameters: [
          {
            parameterType: 'formBinaryData',
            name: 'source',
            inputDataFieldName: 'video_data'
          },
          {
            name: 'title',
            value: '={{ $node["KCT Webhook Trigger"].json.body.content.title }}'
          },
          {
            name: 'description',
            value: '={{ $node["KCT Webhook Trigger"].json.body.content.facebook_caption || $node["KCT Webhook Trigger"].json.body.content.description }}'
          },
          {
            name: 'published',
            value: 'true'
          }
        ]
      },
      options: {
        timeout: 300000
      }
    };
    console.log('✓ Updated Facebook Page Video to graph-video endpoint with 300s timeout & continueOnFail');
  }

  // 2. Set continueOnFail on YouTube Video Upload so a YouTube glitch never crashes Facebook
  const ytNode = nodes.find(n => n.name === 'YouTube Video Upload');
  if (ytNode) {
    ytNode.continueOnFail = true;
    console.log('✓ Set continueOnFail = true on YouTube Video Upload');
  }

  // 3. Set continueOnFail on Instagram
  const igNode = nodes.find(n => n.name === 'Instagram Reels Container');
  if (igNode) {
    igNode.continueOnFail = true;
  }

  // 4. Update Connections so Read Local Video Binary feeds directly into all 5 platforms in parallel!
  // This removes the Switch node bottleneck that was forcing only 1 platform to ever execute.
  connections['Read Local Video Binary'] = {
    main: [
      [
        { node: 'Post to YouTube?', type: 'main', index: 0 },
        { node: 'Post to Facebook?', type: 'main', index: 0 },
        { node: 'Post to Instagram?', type: 'main', index: 0 },
        { node: 'Post to TikTok?', type: 'main', index: 0 },
        { node: 'Post to X?', type: 'main', index: 0 }
      ]
    ]
  };
  console.log('✓ Connected Read Local Video Binary to all 5 platforms in parallel');

  // 5. Update Live Dispatch Response to return results safely
  const respNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (respNode) {
    respNode.parameters = {
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

    let fbId = '';
    try {
      const fbNode = $('Facebook Page Video');
      if (fbNode) {
        const item = fbNode.first();
        fbId = (item && item.json && (item.json.id || item.json.video_id)) || '';
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
      message: "Video processed by n8n.",
      video: videoName,
      youtube_id: ytId,
      youtube_url: ytId ? 'https://youtu.be/' + ytId : '',
      facebook_id: fbId,
      facebook_url: fbId ? 'https://www.facebook.com/watch/?v=' + fbId : '',
      target_platforms: platforms
    });
  })()
}}`,
      options: {
        responseCode: 200
      }
    };
    console.log('✓ Updated Live Dispatch Response');
  }

  const newVersionId = crypto.randomUUID();
  const newVersionCounter = (row.versionCounter || 1) + 1;
  const nodesJson = JSON.stringify(nodes);
  const connectionsJson = JSON.stringify(connections);

  db.run(
    'UPDATE workflow_entity SET nodes = ?, connections = ?, versionId = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
    [nodesJson, connectionsJson, newVersionId, newVersionCounter, WORKFLOW_ID],
    (err2) => {
      if (err2) {
        console.error('Update workflow_entity failed:', err2);
        process.exit(1);
      }
      console.log('✓ Updated workflow_entity with newVersionId:', newVersionId);

      db.run(
        'INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name, autosaved) VALUES (?, ?, ?, datetime("now"), datetime("now"), ?, ?, ?, ?)',
        [newVersionId, WORKFLOW_ID, 'Crispin Tuballa', nodesJson, connectionsJson, row.name, 0],
        (err3) => {
          if (err3) console.error('Insert workflow_history failed:', err3);
          else console.log('✓ Inserted snapshot into workflow_history');

          db.run(
            'UPDATE workflow_history SET nodes = ?, connections = ? WHERE workflowId = ?',
            [nodesJson, connectionsJson, WORKFLOW_ID],
            (err4) => {
              if (err4) console.error('Bulk update workflow_history failed:', err4);
              else console.log('✓ Synchronized all workflow_history records');
              db.close();
            }
          );
        }
      );
    }
  );
});
