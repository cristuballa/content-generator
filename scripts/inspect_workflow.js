const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');
const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT nodes, connections FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Error:', err);
    process.exit(1);
  }
  const nodes = JSON.parse(row.nodes);
  const connections = JSON.parse(row.connections);

  console.log('--- ALL NODE NAMES ---');
  nodes.forEach(n => console.log(n.name, '(' + n.type + ')'));

  console.log('\n--- INSTAGRAM NODES ---');
  const igNodes = nodes.filter(n => n.name.toLowerCase().includes('instagram'));
  console.log(JSON.stringify(igNodes, null, 2));

  console.log('\n--- CONNECTIONS FOR INSTAGRAM ---');
  for (const [k, v] of Object.entries(connections)) {
    if (k.toLowerCase().includes('instagram')) {
      console.log(k, '->', JSON.stringify(v));
    }
    // Also check if any connects TO instagram
    if (v.main) {
      v.main.forEach((targets, idx) => {
        targets.forEach(t => {
          if (t.node.toLowerCase().includes('instagram')) {
            console.log(k, `[out:${idx}] ->`, t.node);
          }
        });
      });
    }
  }

  db.close();
});
