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

  // 1. Remove any old Already Posted nodes if they exist
  nodes = nodes.filter(n => n.name !== 'Already Posted?' && n.name !== 'Already Posted Skip & Respond');

  // 2. Adjust positions
  const readNode = nodes.find(n => n.name === 'Read Local Video Binary');
  if (readNode) readNode.position = [-48, 192];

  const routerNode = nodes.find(n => n.name === 'Platform Switch / Router');
  if (routerNode) routerNode.position = [416, 256];

  const ytNode = nodes.find(n => n.name === 'YouTube Video Upload');
  if (ytNode) ytNode.position = [688, -32];

  const fbNode = nodes.find(n => n.name === 'Facebook Page Video');
  if (fbNode) fbNode.position = [688, 112];

  const igNode = nodes.find(n => n.name === 'Instagram Reels Container');
  if (igNode) igNode.position = [688, 256];

  const ttNode = nodes.find(n => n.name === 'TikTok Creator Post');
  if (ttNode) ttNode.position = [688, 400];

  const xNode = nodes.find(n => n.name === 'X (Twitter) Tweet');
  if (xNode) xNode.position = [688, 544];

  const respNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (respNode) respNode.position = [960, 256];

  // 3. Create "Already Posted?" node
  const ifAlreadyPostedNode = {
    parameters: {
      conditions: {
        boolean: [
          {
            value1: "={{ ($node[\"KCT Webhook Trigger\"].json.body.force_republish !== true) && ($node[\"KCT Webhook Trigger\"].json.body.is_already_posted === true || ($node[\"KCT Webhook Trigger\"].json.body.already_published_platforms && $node[\"KCT Webhook Trigger\"].json.body.target_platforms && $node[\"KCT Webhook Trigger\"].json.body.target_platforms.some(p => $node[\"KCT Webhook Trigger\"].json.body.already_published_platforms.includes(p)))) }}",
            value2: true
          }
        ]
      }
    },
    id: "a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d",
    name: "Already Posted?",
    type: "n8n-nodes-base.if",
    typeVersion: 1,
    position: [176, 192]
  };

  // 4. Create "Already Posted Skip & Respond" node
  const skipRespondNode = {
    parameters: {
      respondWith: "json",
      responseBody: "={\n  \"success\": true,\n  \"already_posted\": true,\n  \"skipped\": true,\n  \"message\": \"Video/image has already been posted to target platform. Dispatch halted to prevent duplicate upload.\",\n  \"video\": \"{{ $node[\"KCT Webhook Trigger\"].json.body.video.filename }}\",\n  \"target_platforms\": {{ JSON.stringify($node[\"KCT Webhook Trigger\"].json.body.target_platforms) }},\n  \"already_published_platforms\": {{ JSON.stringify($node[\"KCT Webhook Trigger\"].json.body.already_published_platforms || []) }}\n}",
      options: {
        responseCode: 200
      }
    },
    id: "f8e7d6c5-b4a3-4210-9876-543210fedcba",
    name: "Already Posted Skip & Respond",
    type: "n8n-nodes-base.respondToWebhook",
    typeVersion: 1,
    position: [416, 64]
  };

  nodes.push(ifAlreadyPostedNode, skipRespondNode);

  // 5. Build Connections
  const connections = {
    "KCT Webhook Trigger": {
      "main": [
        [
          { "node": "Is Dry Run?", "type": "main", "index": 0 }
        ]
      ]
    },
    "Is Dry Run?": {
      "main": [
        [
          { "node": "Dry Run Log & Respond", "type": "main", "index": 0 }
        ],
        [
          { "node": "Read Local Video Binary", "type": "main", "index": 0 }
        ]
      ]
    },
    "Read Local Video Binary": {
      "main": [
        [
          { "node": "Already Posted?", "type": "main", "index": 0 }
        ]
      ]
    },
    "Already Posted?": {
      "main": [
        [
          { "node": "Already Posted Skip & Respond", "type": "main", "index": 0 }
        ],
        [
          { "node": "Platform Switch / Router", "type": "main", "index": 0 }
        ]
      ]
    },
    "Platform Switch / Router": {
      "main": [
        [
          { "node": "YouTube Video Upload", "type": "main", "index": 0 }
        ],
        [
          { "node": "Facebook Page Video", "type": "main", "index": 0 }
        ],
        [
          { "node": "Instagram Reels Container", "type": "main", "index": 0 }
        ],
        [
          { "node": "TikTok Creator Post", "type": "main", "index": 0 }
        ],
        [
          { "node": "X (Twitter) Tweet", "type": "main", "index": 0 }
        ]
      ]
    },
    "YouTube Video Upload": {
      "main": [
        [
          { "node": "Live Dispatch Response", "type": "main", "index": 0 }
        ]
      ]
    },
    "Facebook Page Video": {
      "main": [
        [
          { "node": "Live Dispatch Response", "type": "main", "index": 0 }
        ]
      ]
    },
    "Instagram Reels Container": {
      "main": [
        [
          { "node": "Live Dispatch Response", "type": "main", "index": 0 }
        ]
      ]
    },
    "TikTok Creator Post": {
      "main": [
        [
          { "node": "Live Dispatch Response", "type": "main", "index": 0 }
        ]
      ]
    },
    "X (Twitter) Tweet": {
      "main": [
        [
          { "node": "Live Dispatch Response", "type": "main", "index": 0 }
        ]
      ]
    }
  };

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
      console.log('✓ Updated workflow_entity with Already Posted guard node');

      db.run(
        'INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name, autosaved) VALUES (?, ?, ?, datetime("now"), datetime("now"), ?, ?, ?, ?)',
        [newVersionId, WORKFLOW_ID, 'Crispin Tuballa', nodesJson, connectionsJson, row.name, 0],
        (err3) => {
          if (err3) console.error('Insert workflow_history failed:', err3);
          else console.log('✓ Inserted new version snapshot into workflow_history');

          db.run(
            'UPDATE workflow_history SET nodes = ?, connections = ? WHERE workflowId = ?',
            [nodesJson, connectionsJson, WORKFLOW_ID],
            (err4) => {
              if (err4) console.error('Sync workflow_history failed:', err4);
              else console.log('✓ Synchronized all workflow_history records');
              db.close();
            }
          );
        }
      );
    }
  );
});
