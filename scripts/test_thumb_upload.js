const crypto = require('crypto');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const testWorkflow = {
  name: 'Test Thumbnail Upload',
  active: false,
  nodes: [
    {
      parameters: {
        filePath: '/data/projects/BHRS-Youtube/9-The_Covenant_of_Pieces/thumbnail_option_1.jpg',
        dataPropertyName: 'thumbnail_data'
      },
      id: 'test-read-thumb',
      name: 'Read Thumbnail',
      type: 'n8n-nodes-base.readBinaryFile',
      typeVersion: 1,
      position: [100, 100]
    },
    {
      parameters: {
        method: 'POST',
        url: 'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=kyj8xDnH4mA&uploadType=media',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'youTubeOAuth2Api',
        sendBody: true,
        contentType: 'binaryData',
        inputDataFieldName: 'thumbnail_data',
        options: {}
      },
      id: 'test-upload-thumb',
      name: 'Upload Thumbnail',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [300, 100],
      credentials: {
        youTubeOAuth2Api: {
          id: 'zKTSb5kFkzMhCn0w',
          name: 'YouTube account'
        }
      }
    }
  ],
  connections: {
    'Read Thumbnail': {
      main: [
        [
          {
            node: 'Upload Thumbnail',
            type: 'main',
            index: 0
          }
        ]
      ]
    }
  }
};

const id = 'test_thumb_upload_01';
db.run(
  'INSERT OR REPLACE INTO workflow_entity (id, name, active, nodes, connections, versionCounter, versionId, createdAt, updatedAt) VALUES (?, ?, 0, ?, ?, 1, ?, datetime(), datetime())',
  [id, testWorkflow.name, JSON.stringify(testWorkflow.nodes), JSON.stringify(testWorkflow.connections), crypto.randomUUID()],
  function(err) {
    if (err) console.error('Insert error:', err);
    else console.log('Test workflow created successfully!');
    db.close();
  }
);
