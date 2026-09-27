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

  // 1. Update Facebook Page Video Node
  const fbNode = nodes.find(n => n.name === 'Facebook Page Video');
  if (fbNode) {
    fbNode.typeVersion = 4.2;
    fbNode.parameters = {
      method: 'POST',
      url: `https://graph.facebook.com/v20.0/${PAGE_ID}/videos`,
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
      options: {}
    };
    console.log('✓ Updated Facebook Page Video node with permanent token and Page ID');
  } else {
    console.warn('⚠️ Facebook Page Video node not found');
  }

  // 2. Update Live Dispatch Response to report back Facebook Video ID and URL
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
      message: "Video successfully processed by n8n.",
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
    console.log('✓ Updated Live Dispatch Response to return facebook_id and facebook_url');
  }

  const newVersionId = crypto.randomUUID();
  const newVersionCounter = (row.versionCounter || 1) + 1;
  const nodesJson = JSON.stringify(nodes);
  const connectionsJson = row.connections;

  db.run(
    'UPDATE workflow_entity SET nodes = ?, versionId = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
    [nodesJson, newVersionId, newVersionCounter, WORKFLOW_ID],
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
            'UPDATE workflow_history SET nodes = ? WHERE workflowId = ?',
            [nodesJson, WORKFLOW_ID],
            (err4) => {
              if (err4) console.error('Bulk update workflow_history failed:', err4);
              else console.log('✓ Synchronized all workflow_history records for workflow');
              db.close();
            }
          );
        }
      );
    }
  );
});
