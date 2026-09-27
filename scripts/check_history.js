const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');
const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.all('SELECT versionId, createdAt, nodes FROM workflow_history WHERE workflowId = ? ORDER BY createdAt ASC LIMIT 5', [WORKFLOW_ID], (err, rows) => {
  if (err) return console.error(err);
  rows.forEach(r => {
    const nodes = JSON.parse(r.nodes);
    const ig = nodes.find(n => n.name && n.name.toLowerCase().includes('instagram reels container'));
    console.log(r.createdAt, 'IG Container:', JSON.stringify(ig?.parameters));
  });
  db.close();
});
