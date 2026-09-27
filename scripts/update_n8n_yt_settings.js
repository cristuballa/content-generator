const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const WORKFLOW_ID = 'YCJAtMTxSP0qm3mt';

db.get('SELECT id, name, active, nodes, connections, versionCounter, versionId, activeVersionId FROM workflow_entity WHERE id = ?', [WORKFLOW_ID], (err, row) => {
  if (err || !row) {
    console.error('Failed to find workflow:', err);
    process.exit(1);
  }

  let nodes = JSON.parse(row.nodes);
  const ytNode = nodes.find(n => n.name === 'YouTube Video Upload');

  if (!ytNode) {
    console.error('YouTube Video Upload node not found!');
    process.exit(1);
  }

  // Update options on YouTube Video Upload node
  ytNode.parameters = ytNode.parameters || {};
  ytNode.parameters.options = ytNode.parameters.options || {};
  
  // 1. Privacy status -> Public by default (or expression from platform config)
  ytNode.parameters.options.privacyStatus = '={{ $node["KCT Webhook Trigger"].json.body.platform_configs?.youtube?.privacy_status || "public" }}';
  
  // 2. Audience -> Not made for kids
  ytNode.parameters.options.selfDeclaredMadeForKids = false;

  // 3. Description -> YouTube Shorts URL-safe description (replaces all raw URLs with Link in channel bio)
  ytNode.parameters.options.description = '={{ ($node["KCT Webhook Trigger"].json.body.content.youtube_description || $node["KCT Webhook Trigger"].json.body.content.description || "").replace(/:?\\s*https?:\\/\\/\\S+/gi, " 🔗 (Link in channel bio)").replace(/:?\\s*www\\.\\S+/gi, " 🔗 (Link in channel bio)") }}';

  console.log('Updated YouTube Video Upload node parameters:', JSON.stringify(ytNode.parameters, null, 2));

  const updatedNodesStr = JSON.stringify(nodes);
  const newCounter = (row.versionCounter || 1) + 1;

  db.serialize(() => {
    db.run(
      'UPDATE workflow_entity SET nodes = ?, versionCounter = ?, updatedAt = datetime("now") WHERE id = ?',
      [updatedNodesStr, newCounter, WORKFLOW_ID],
      function(updateErr) {
        if (updateErr) {
          console.error('Error updating workflow_entity:', updateErr);
          process.exit(1);
        }
        console.log('Successfully updated workflow_entity!');
      }
    );

    db.run(
      'UPDATE workflow_history SET nodes = ? WHERE workflowId = ?',
      [updatedNodesStr, WORKFLOW_ID],
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
