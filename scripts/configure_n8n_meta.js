const crypto = require('crypto');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT id, name, active, nodes, connections, versionCounter FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  let nodes = JSON.parse(row.nodes);
  let connections = JSON.parse(row.connections);

  // 1. Ensure YouTube Video Upload has continueOnFail: true
  const ytNode = nodes.find(n => n.name === 'YouTube Video Upload');
  if (ytNode) {
    ytNode.continueOnFail = true;
    console.log('✓ Set continueOnFail = true on YouTube Video Upload');
  }

  // 2. Add or update 'Post to Meta?' IF node
  let postToMetaNode = nodes.find(n => n.name === 'Post to Meta?');
  if (!postToMetaNode) {
    postToMetaNode = {
      id: crypto.randomUUID(),
      name: 'Post to Meta?',
      type: 'n8n-nodes-base.if',
      typeVersion: 1,
      position: [400, 200],
      parameters: {
        conditions: {
          boolean: [
            {
              value1: `={{
  const plats = $node["KCT Webhook Trigger"].json.body.target_platforms || [];
  plats.includes("facebook") || plats.includes("instagram")
}}`,
              value2: true
            }
          ]
        }
      }
    };
    nodes.push(postToMetaNode);
    console.log('✓ Created Post to Meta? IF node');
  } else {
    postToMetaNode.parameters = {
      conditions: {
        boolean: [
          {
            value1: `={{
  const plats = $node["KCT Webhook Trigger"].json.body.target_platforms || [];
  plats.includes("facebook") || plats.includes("instagram")
}}`,
            value2: true
          }
        ]
      }
    };
    console.log('✓ Updated Post to Meta? IF node');
  }

  // 3. Add or update 'Publish to Meta (FB & IG)' Execute Command node
  let publishMetaNode = nodes.find(n => n.name === 'Publish to Meta (FB & IG)');
  const commandExpr = `={{
  const trigger = $node["KCT Webhook Trigger"].json.body;
  const projectPath = trigger.project && trigger.project.path ? trigger.project.path.replace(/\\\\/g, '/').split('/').filter(Boolean).pop() : 'Bible Hidden Secrets Revealed';
  const filePath = trigger.video && trigger.video.docker_path ? trigger.video.docker_path : ('/data/projects/' + projectPath + '/' + trigger.video.rel_path);
  
  const payload = {
    filePath: filePath,
    title: trigger.content && trigger.content.title || '',
    facebookCaption: (trigger.content && (trigger.content.facebook_caption || trigger.content.description)) || '',
    instagramCaption: (trigger.content && (trigger.content.instagram_caption || trigger.content.description)) || '',
    targetPlatforms: trigger.target_platforms || ['facebook', 'instagram']
  };

  'node /data/projects/AI-Content-Generation-Pipeline/scripts/publish_meta.js ' + Buffer.from(JSON.stringify(payload)).toString('base64');
}}`;

  if (!publishMetaNode) {
    publishMetaNode = {
      id: crypto.randomUUID(),
      name: 'Publish to Meta (FB & IG)',
      type: 'n8n-nodes-base.executeCommand',
      typeVersion: 1,
      continueOnFail: true,
      position: [650, 150],
      parameters: {
        command: commandExpr
      }
    };
    nodes.push(publishMetaNode);
    console.log('✓ Created Publish to Meta (FB & IG) Execute Command node');
  } else {
    publishMetaNode.continueOnFail = true;
    publishMetaNode.parameters = {
      command: commandExpr
    };
    console.log('✓ Updated Publish to Meta (FB & IG) node');
  }

  // 4. Update Live Dispatch Response
  const respNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (respNode) {
    respNode.position = [900, 200];
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
    let fbUrl = '';
    let igId = '';
    let igUrl = '';

    try {
      const metaNode = $('Publish to Meta (FB & IG)');
      if (metaNode) {
        const item = metaNode.first();
        let parsed = null;
        if (item && item.json) {
          if (item.json.stdout) {
            try { parsed = JSON.parse(item.json.stdout.trim()); } catch(e) {}
          } else if (item.json.facebook_id || item.json.instagram_id) {
            parsed = item.json;
          }
        }
        if (parsed) {
          fbId = parsed.facebook_id || '';
          fbUrl = parsed.facebook_url || (fbId ? 'https://www.facebook.com/watch/?v=' + fbId : '');
          igId = parsed.instagram_id || '';
          igUrl = parsed.instagram_url || '';
        }
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
      facebook_url: fbUrl,
      instagram_id: igId,
      instagram_url: igUrl,
      target_platforms: platforms
    });
  })()
}}`,
      options: {
        responseCode: 200
      }
    };
    console.log('✓ Updated Live Dispatch Response node');
  }

  // 5. Wire the clean sequential/parallel pipeline
  // Read Local Video Binary -> Post to YouTube?
  connections['Read Local Video Binary'] = {
    main: [
      [
        { node: 'Post to YouTube?', type: 'main', index: 0 }
      ]
    ]
  };

  // Post to YouTube? [0 (true) -> YouTube Video Upload], [1 (false) -> Post to Meta?]
  connections['Post to YouTube?'] = {
    main: [
      [
        { node: 'YouTube Video Upload', type: 'main', index: 0 }
      ],
      [
        { node: 'Post to Meta?', type: 'main', index: 0 }
      ]
    ]
  };

  // YouTube Video Upload -> Has YouTube Thumbnail?
  connections['YouTube Video Upload'] = {
    main: [
      [
        { node: 'Has YouTube Thumbnail?', type: 'main', index: 0 }
      ]
    ]
  };

  // Has YouTube Thumbnail? [0 (true) -> Read Thumbnail Binary], [1 (false) -> Post to Meta?]
  connections['Has YouTube Thumbnail?'] = {
    main: [
      [
        { node: 'Read Thumbnail Binary', type: 'main', index: 0 }
      ],
      [
        { node: 'Post to Meta?', type: 'main', index: 0 }
      ]
    ]
  };

  // Read Thumbnail Binary -> Upload YouTube Thumbnail
  connections['Read Thumbnail Binary'] = {
    main: [
      [
        { node: 'Upload YouTube Thumbnail', type: 'main', index: 0 }
      ]
    ]
  };

  // Upload YouTube Thumbnail -> Post to Meta?
  connections['Upload YouTube Thumbnail'] = {
    main: [
      [
        { node: 'Post to Meta?', type: 'main', index: 0 }
      ]
    ]
  };

  // Post to Meta? [0 (true) -> Publish to Meta (FB & IG)], [1 (false) -> Live Dispatch Response]
  connections['Post to Meta?'] = {
    main: [
      [
        { node: 'Publish to Meta (FB & IG)', type: 'main', index: 0 }
      ],
      [
        { node: 'Live Dispatch Response', type: 'main', index: 0 }
      ]
    ]
  };

  // Publish to Meta (FB & IG) -> Live Dispatch Response
  connections['Publish to Meta (FB & IG)'] = {
    main: [
      [
        { node: 'Live Dispatch Response', type: 'main', index: 0 }
      ]
    ]
  };

  console.log('✓ Successfully rewired pipeline connections');

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
      console.log('✓ Updated workflow_entity with versionId:', newVersionId);

      db.run(
        'INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name, autosaved) VALUES (?, ?, ?, datetime("now"), datetime("now"), ?, ?, ?, ?)',
        [newVersionId, WORKFLOW_ID, 'Crispin Tuballa', nodesJson, connectionsJson, row.name, 0],
        (err3) => {
          if (err3) console.error('Insert workflow_history failed:', err3);
          else console.log('✓ Snapshot created in workflow_history');

          db.run(
            'UPDATE workflow_history SET nodes = ?, connections = ? WHERE workflowId = ?',
            [nodesJson, connectionsJson, WORKFLOW_ID],
            (err4) => {
              if (err4) console.error('Bulk update workflow_history failed:', err4);
              else console.log('✓ Synchronized all workflow history snapshots');
              db.close();
            }
          );
        }
      );
    }
  );
});
