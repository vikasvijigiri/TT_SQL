import fs from 'fs';

const content = fs.readFileSync('c:/Users/VikasVijigiri/Documents/TT_SQL/frontend/src/App.jsx', 'utf8');

let depth = 0;
let lines = content.split('\n');

for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    // Simple bracket counting, ignore strings/comments for now
    for (let char of line) {
        if (char === '{') depth++;
        if (char === '}') depth--;
        if (depth < 0) {
            console.log(`NEGATIVE DEPTH at line ${i + 1}: ${line.trim()}`);
            depth = 0; // Reset to keep going
        }
    }
}
console.log(`Final depth: ${depth}`);
