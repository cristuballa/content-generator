const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');
db.all('SELECT * FROM workflow_entity WHERE id = ?', ['YCJAtMTxSP0qm3mt'], (err, rows) => {
  if (err || !rows.length) {
    console.error('Error fetching workflow:', err);
    process.exit(1);
  }
  const row = rows[0];
  const out = [{
    updatedAt: row.updatedAt,
    createdAt: row.createdAt,
    id: row.id,
    name: row.name,
    description: row.description,
    active: row.active === 1,
    isArchived: row.isArchived === 1,
    nodes: JSON.parse(row.nodes),
    connections: JSON.parse(row.connections),
    settings: JSON.parse(row.settings || '{}'),
    staticData: row.staticData ? JSON.parse(row.staticData) : null,
    meta: row.meta ? JSON.parse(row.meta) : null,
    pinData: row.pinData ? JSON.parse(row.pinData) : {},
    versionId: row.versionId,
    triggerCount: row.triggerCount || 0
  }];
  process.stdout.write(JSON.stringify(out, null, 2));
  db.close();
});
