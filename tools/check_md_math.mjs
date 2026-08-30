#!/usr/bin/env node
// MD/GFM LaTeX math sanity checker.
// Strict mode: needs katex (npm i katex) for full parse; always checks GFM structure rules.
// usage: node check_md_math.mjs file.md [files...]
import fs from 'node:fs';

let katex = null;
try {
  katex = (await import('/tmp/opencode/kx/node_modules/katex/dist/katex.mjs')).default;
} catch {
  try {
    katex = (await import('/tmp/opencode/kx/node_modules/katex/dist/katex.js')).default;
  } catch {}
}

const files = process.argv.slice(2);
if (!files.length) { console.error('usage: node check_md_math.mjs <file.md> [...]'); process.exit(2); }

const $ = (s) => s.replaceAll('\\', '\\\\');
let total = 0;
const err = [];

function render(expr, display) {
  if (!katex) return true;
  try { katex.renderToString(expr, { throwOnError: true, displayMode: display }); return true; }
  catch (e) { err.push(`KATEX(${display ? 'display' : 'inline'}): ${expr.slice(0, 100)} → ${e.message}`); return false; }
}

for (const f of files) {
  const lines = fs.readFileSync(f, 'utf8').split('\n');
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith('```')) { inFence = !inFence; continue; }
    if (inFence) continue;

    // 1) indented block $$
    if (/^[ \t]+\$\$/.test(l)) { err.push(`${f}:${i + 1} INDENTED-BLOCK ($$ with leading spaces)`); total++; }
    // 2) block $$ on the same line as other text (not alone)
    if (/\S\$\$/.test(l) && !/^[ \t]*\$\$[\s\S]*\$\$[ \t]*$/.test(l)) {
      // allowed only if this is a standalone paragraph "$$expr$$"
      if (!/^[ \t]*\$\$[^\n]*\$\$[ \t]*$/.test(l)) {
        err.push(`${f}:${i + 1} NOT-ALONE-BLOCK ($$ mixed with text)`); total++;
      }
    }
    // 3) inline touching alnum
    const inl = l.match(/\$(?!\$)[^$\n]+\$(?!\$)/g) || [];
    for (const s of inl) {
      const idx = l.indexOf(s);
      const a = l[idx + s.length] || '';
      const b = l[idx - 1] || '';
      if (/[0-9A-Za-z]/.test(a)) { err.push(`${f}:${i + 1} TOUCH-AFTER: ${l.slice(Math.max(0, idx - 12))}`); total++; }
      if (/[0-9A-Za-z]/.test(b)) { err.push(`${f}:${i + 1} TOUCH-BEFORE: ${l.slice(Math.max(0, idx - 12))}`); total++; }
      render(s.slice(1, -1), false);
    }
    // 4) unclosed inline math at end of line (single trailing $, not $$)
    const stripped = l.replace(/\$\$[\s\S]*?\$\$/g, '');
    const singleCount = (stripped.match(/(?<!\$)\$(?!\$)/g) || []).length;
    if (singleCount % 2 === 1) { err.push(`${f}:${i + 1} UNCLOSED-DOLLAR (odd single $)`); total++; }
  }
  // 5) display blocks: blank-line isolation + render check (across whole file)
  const src = fs.readFileSync(f, 'utf8');
  const lines2 = src.split('\n');
  let inFence2 = false;
  for (let i = 0; i < lines2.length; i++) {
    if (lines2[i].trim().startsWith('```')) { inFence2 = !inFence2; continue; }
    if (inFence2) continue;
    const t = lines2[i].trim();
    const isOpen = t.startsWith('$$') && (t.replaceAll('$$', '').trim() === '' || /^\$\$[^\n]*\$\$/.test(t));
    if (!isOpen) continue;
    // opening/complete block
    let end = i;
    if (t === '$$') {
      let j = i + 1;
      while (j < lines2.length && lines2[j].trim() !== '$$') j++;
      if (j < lines2.length) end = j; else { err.push(`${f}:${i + 1} BLOCK-PROBLEM ($$ never closed)`); total++; }
      // GitHub MathJax: a blank line inside the block splits it; flag it.
      for (let k = i; k <= end; k++) {
        if (lines2[k].trim() === '') { err.push(`${f}:${k + 1} BLANK-INSIDE (blank line inside $$...$$)`); total++; }
      }
    } else {
      // inline $$...$$ on one line
      end = i;
    }
    const before = lines2[i - 1] ?? '';
    const after = lines2[end + 1] ?? '';
    if (before.trim() !== '') { err.push(`${f}:${i + 1} BLANK-PROBLEM (no blank line BEFORE block)`); total++; }
    if (after.trim() !== '') { err.push(`${f}:${end + 1} BLANK-PROBLEM (no blank line AFTER block)`); total++; }
    const expr = lines2.slice(i, end + 1).join(' ').replace(/\$\$/g, '');
    render(expr, true);
    i = end;
  }
}

if (total > 0) {
  console.error(`MATH CHECKS FAILED: ${total} issue(s)`);
  for (const e of err) console.error(' - ' + e);
  process.exit(1);
}
if (!katex) console.log('OK (structural checks only — install katex for full parse)');
else console.log('OK — all math parsed by KaTeX, 0 issues.');
