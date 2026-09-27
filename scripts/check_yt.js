const fs = require('fs');
const path = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file++++home+runner+_work+n8n+n8n+packages+nodes-base/node_modules/n8n-nodes-base/dist/nodes/Google/YouTube/YouTube.node.js';
const code = fs.readFileSync(path, 'utf8');
const p = code.indexOf("operation === 'upload'");
console.log(code.slice(p, p + 1500));
