const fs = require('fs');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT id, name, active, nodes, connections, settings, staticData, pinData, versionCounter, versionId, activeVersionId FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  let nodes = JSON.parse(row.nodes);
  let connections = JSON.parse(row.connections);

  // 1. Check or update Read Local Video Binary
  const readVideoNode = nodes.find(n => n.name === 'Read Local Video Binary');
  if (readVideoNode) {
    readVideoNode.parameters = readVideoNode.parameters || {};
    readVideoNode.parameters.filePath = '={{ $node["KCT Webhook Trigger"].json.body.video.docker_path || (\'/data/projects/\' + ($node["KCT Webhook Trigger"].json.body.project && $node["KCT Webhook Trigger"].json.body.project.path ? $node["KCT Webhook Trigger"].json.body.project.path.replace(/\\\\/g, \'/\').split(\'/\').filter(Boolean).pop() : ($node["KCT Webhook Trigger"].json.body.project ? $node["KCT Webhook Trigger"].json.body.project.name : \'Bible Hidden Secrets Revealed\')) + \'/\' + $node["KCT Webhook Trigger"].json.body.video.rel_path) }}';
  }

  // 2. Update Live Dispatch Response
  const respNode = nodes.find(n => n.name === 'Live Dispatch Response');
  if (respNode) {
    respNode.position = [1600, 256];
    respNode.parameters = respNode.parameters || {};
    respNode.parameters.responseBody = '={\n  "success": true,\n  "message": "Video successfully processed by n8n.",\n  "video": "{{ $node[\\"KCT Webhook Trigger\\"].json.body.video.filename }}",\n  "youtube_id": "{{ $node[\\"YouTube Video Upload\\"].json.uploadId || $node[\\"YouTube Video Upload\\"].json.id || $json.uploadId || $json.id }}",\n  "youtube_url": "https://youtu.be/{{ $node[\\"YouTube Video Upload\\"].json.uploadId || $node[\\"YouTube Video Upload\\"].json.id || $json.uploadId || $json.id }}",\n  "target_platforms": {{ JSON.stringify($node[\\"KCT Webhook Trigger\\"].json.body.target_platforms) }}\n}';
  }

  // 3. Remove existing thumbnail nodes if already present so script is idempotent
  nodes = nodes.filter(n => !['Has YouTube Thumbnail?', 'Read Thumbnail Binary', 'Upload YouTube Thumbnail'].includes(n.name));

  // 4. Create new thumbnail nodes
  const ifThumbNode = {
    parameters: {
      conditions: {
        boolean: [
          {
            value1: '={{ Boolean($node["KCT Webhook Trigger"].json.body.video?.has_custom_thumbnail && ($node["KCT Webhook Trigger"].json.body.video?.thumbnail_docker_path || $node["KCT Webhook Trigger"].json.body.video?.thumbnail_path)) }}',
            value2: true
          }
        ]
      }
    },
    id: 'yt-thumb-if-000000001',
    name: 'Has YouTube Thumbnail?',
    type: 'n8n-nodes-base.if',
    typeVersion: 1,
    position: [920, -32]
  };

  const readThumbNode = {
    parameters: {
      filePath: '={{ $node["KCT Webhook Trigger"].json.body.video.thumbnail_docker_path || $node["KCT Webhook Trigger"].json.body.video.thumbnail_path }}',
      dataPropertyName: 'thumbnail_data'
    },
    id: 'yt-thumb-read-0000001',
    name: 'Read Thumbnail Binary',
    type: 'n8n-nodes-base.readBinaryFile',
    typeVersion: 1,
    position: [1140, -112]
  };

  const uploadThumbNode = {
    parameters: {
      method: 'POST',
      url: '=https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={{ $node["YouTube Video Upload"].json.uploadId || $node["YouTube Video Upload"].json.id || $json.uploadId || $json.id }}&uploadType=media',
      authentication: 'predefinedCredentialType',
      nodeCredentialType: 'youTubeOAuth2Api',
      sendBody: true,
      contentType: 'binaryData',
      inputDataFieldName: 'thumbnail_data',
      options: {}
    },
    continueOnFail: true,
    id: 'yt-thumb-upload-00001',
    name: 'Upload YouTube Thumbnail',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.1,
    position: [1360, -112],
    credentials: {
      youTubeOAuth2Api: {
        id: 'zKTSb5kFkzMhCn0w',
        name: 'YouTube account'
      }
    }
  };

  nodes.push(ifThumbNode, readThumbNode, uploadThumbNode);

  // 5. Update connections
  // YouTube Video Upload -> Has YouTube Thumbnail?
  connections['YouTube Video Upload'] = {
    main: [
      [
        {
          node: 'Has YouTube Thumbnail?',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  // Has YouTube Thumbnail? -> True to Read Thumbnail Binary, False to Live Dispatch Response
  connections['Has YouTube Thumbnail?'] = {
    main: [
      [
        {
          node: 'Read Thumbnail Binary',
          type: 'main',
          index: 0
        }
      ],
      [
        {
          node: 'Live Dispatch Response',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  // Read Thumbnail Binary -> Upload YouTube Thumbnail
  connections['Read Thumbnail Binary'] = {
    main: [
      [
        {
          node: 'Upload YouTube Thumbnail',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  // Upload YouTube Thumbnail -> Live Dispatch Response
  connections['Upload YouTube Thumbnail'] = {
    main: [
      [
        {
          node: 'Live Dispatch Response',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  console.log('Total nodes after update:', nodes.length);

  const updatedNodesStr = JSON.stringify(nodes);
  const updatedConnsStr = JSON.stringify(connections);
  const newCounter = (row.versionCounter || 1) + 1;

  db.serialize(() => {
    db.run(
      'UPDATE workflow_entity SET nodes = ?, connections = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
      [updatedNodesStr, updatedConnsStr, newCounter, WORKFLOW_ID],
      function(updateErr) {
        if (updateErr) {
          console.error('Error updating workflow_entity:', updateErr);
          process.exit(1);
        }
        console.log('Successfully updated workflow_entity with YouTube thumbnail pipeline!');
      }
    );

    db.run(
      'UPDATE workflow_history SET nodes = ?, connections = ? WHERE workflowId = ?',
      [updatedNodesStr, updatedConnsStr, WORKFLOW_ID],
      function(histErr) {
        if (histErr) {
          console.error('Error updating workflow_history:', histErr);
          process.exit(1);
        }
        console.log('Successfully updated workflow_history for all versions!');
        db.close();
      }
    );
  });
});
