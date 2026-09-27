const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');
const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT nodes FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  const nodes = JSON.parse(row.nodes);
  const n = nodes.find(x => x.name === 'Read Local Video Binary');
  console.log('Read Local Video Binary:', JSON.stringify(n, null, 2));
  db.close();
});
