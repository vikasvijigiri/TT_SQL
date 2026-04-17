import fs from 'fs';

const content = fs.readFileSync('c:/Users/VikasVijigiri/Documents/TT_SQL/frontend/src/App.jsx', 'utf8');
const lines = content.split('\n');

let bDepth = 0; // Brace depth {}
let pDepth = 0; // Paren depth ()

for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const prevB = bDepth;
    const prevP = pDepth;
    
    for (let char of line) {
        if (char === '{') bDepth++;
        if (char === '}') bDepth--;
        if (char === '(') pDepth++;
        if (char === ')') pDepth--;
    }
    
    if (bDepth < 0) {
        console.log(`[BRACE ERROR] Line ${i + 1}: Negative depth detected! Resetting. Current depth before line was ${prevB}. Line: ${line.trim()}`);
        bDepth = 0;
    }
    if (pDepth < 0) {
        console.log(`[PAREN ERROR] Line ${i + 1}: Negative depth detected! Resetting. Current depth before line was ${prevP}. Line: ${line.trim()}`);
        pDepth = 0;
    }
}
console.log(`Final Balances - Brackets: ${bDepth}, Parentheses: ${pDepth}`);
