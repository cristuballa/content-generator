const crypto = require('crypto');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT id, name, active, nodes, connections, versionCounter FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  const nodes = JSON.parse(row.nodes);
  
  // 1. Update Is Dry Run?
  const isDryRunNode = nodes.find(n => n.name === 'Is Dry Run?');
  if (isDryRunNode) {
    isDryRunNode.parameters = {
      conditions: {
        boolean: [
          {
            value1: "={{ $json.body.dry_run !== false || $json.body.event === 'test_ping' || !$json.body.video }}",
            value2: true
          }
        ]
      }
    };
    console.log('✓ Updated Is Dry Run? node');
  }

  // 2. Update Read Local Video Binary
  const readNode = nodes.find(n => n.name === 'Read Local Video Binary');
  if (readNode) {
    readNode.parameters = {
      filePath: "={{ '/data/projects/' + ($node[\"KCT Webhook Trigger\"].json.body.project ? $node[\"KCT Webhook Trigger\"].json.body.project.name : 'Bible Hidden Secrets Revealed') + '/' + $node[\"KCT Webhook Trigger\"].json.body.video.rel_path }}",
      dataPropertyName: "video_data"
    };
    console.log('✓ Updated Read Local Video Binary node');
  }

  // 3. Update Platform Switch / Router
  const switchNode = nodes.find(n => n.name === 'Platform Switch / Router');
  if (switchNode) {
    switchNode.parameters = {
      dataType: "string",
      value1: "={{ $node[\"KCT Webhook Trigger\"].json.body.target_platforms ? $node[\"KCT Webhook Trigger\"].json.body.target_platforms.join(',') : '' }}",
      rules: {
        rules: [
          { operation: "contains", value2: "youtube" },
          { operation: "contains", value2: "facebook", output: 1 },
          { operation: "contains", value2: "instagram", output: 2 },
          { operation: "contains", value2: "tiktok", output: 3 },
          { operation: "contains", value2: "x", output: 4 }
        ]
      }
    };
    console.log('✓ Updated Platform Switch / Router node');
  }

  // 4. Update YouTube Video Upload
  const ytNode = nodes.find(n => n.name === 'YouTube Video Upload');
  if (ytNode) {
    ytNode.parameters = {
      resource: "video",
      operation: "upload",
      title: "={{ $node[\"KCT Webhook Trigger\"].json.body.content.title }}",
      regionCode: "NZ",
      categoryId: "27",
      binaryProperty: "video_data",
      options: {
        description: "={{ $node[\"KCT Webhook Trigger\"].json.body.content.description }}",
        privacyStatus: "unlisted",
        tags: "={{ $node[\"KCT Webhook Trigger\"].json.body.content.tags ? $node[\"KCT Webhook Trigger\"].json.body.content.tags.join(',') : '' }}"
      }
    };
    console.log('✓ Updated YouTube Video Upload node');
  }

  // 5. Update Live Dispatch Response
  const respNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (respNode) {
    respNode.parameters = {
      respondWith: "json",
      responseBody: "={\n  \"success\": true,\n  \"message\": \"Video successfully processed by n8n.\",\n  \"video\": \"{{ $node[\"KCT Webhook Trigger\"].json.body.video.filename }}\",\n  \"youtube_id\": \"{{ $json.uploadId || $json.id }}\",\n  \"youtube_url\": \"https://youtu.be/{{ $json.uploadId || $json.id }}\",\n  \"target_platforms\": {{ JSON.stringify($node[\"KCT Webhook Trigger\"].json.body.target_platforms) }}\n}",
      options: {
        responseCode: 200
      }
    };
    console.log('✓ Updated Live Dispatch Response node');
  }

  const newVersionId = crypto.randomUUID();
  const newVersionCounter = (row.versionCounter || 1) + 1;
  const nodesJson = JSON.stringify(nodes);
  const connectionsJson = row.connections;

  // Update workflow_entity
  db.run(
    'UPDATE workflow_entity SET nodes = ?, versionId = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
    [nodesJson, newVersionId, newVersionCounter, WORKFLOW_ID],
    (err2) => {
      if (err2) {
        console.error('Update workflow_entity failed:', err2);
        process.exit(1);
      }
      console.log('✓ Updated workflow_entity with newVersionId:', newVersionId);

      // Also insert into workflow_history
      db.run(
        'INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name, autosaved) VALUES (?, ?, ?, datetime("now"), datetime("now"), ?, ?, ?, ?)',
        [newVersionId, WORKFLOW_ID, 'Crispin Tuballa', nodesJson, connectionsJson, row.name, 0],
        (err3) => {
          if (err3) {
            console.error('Insert workflow_history failed:', err3);
          } else {
            console.log('✓ Inserted snapshot into workflow_history');
          }

          // Also update all existing history records for this workflow as a safeguard
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
