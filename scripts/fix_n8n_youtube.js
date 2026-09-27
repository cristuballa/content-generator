const fs = require('fs');

const targetFile = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file++++home+runner+_work+n8n+n8n+packages+nodes-base/node_modules/n8n-nodes-base/dist/nodes/Google/YouTube/YouTube.node.js';

let code = fs.readFileSync(targetFile, 'utf8');
const lines = code.split('\n');

for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes("'Content-Range':")) {
    console.log(`Found Content-Range at line ${i+1}: ${lines[i]}`);
    lines[i] = "                                            'Content-Range': `bytes ${offset}-${nextOffset - 1}/${contentLength}`,";
    console.log(`Replaced with: ${lines[i]}`);
  }
}

fs.writeFileSync(targetFile, lines.join('\n'), 'utf8');
console.log("Updated file successfully!");
