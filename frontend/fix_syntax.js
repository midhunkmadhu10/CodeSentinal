const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src', 'app', 'analyze', 'page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

// Fix escaped backticks: \` -> `
content = content.replace(/\\`/g, '`');

// Fix escaped template expressions: \${ -> ${
content = content.replace(/\\\$\{/g, '${');

// Also fix \\n inside split calls that should be \n
content = content.replace(/rules\.split\('\\\\\\\\n'\)/g, "rules.split('\\n')");

fs.writeFileSync(filePath, content, 'utf8');
console.log('Fixed escaped template literals in page.tsx');
