import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../../app/web/app.js', import.meta.url), 'utf8');

assert.match(
  source,
  /lifecycleGeneration\s*:\s*\d+/,
  'dashboard state must track a lifecycle generation so pre-navigation async work can be invalidated',
);
assert.match(
  source,
  /function\s+isCurrentGeneration\s*\(/,
  'async UI mutations must have a shared current-generation guard',
);
assert.match(
  source,
  /function\s+suspendPage\s*\([^)]*\)\s*\{[\s\S]*lifecycleGeneration\s*\+=\s*1/,
  'pagehide must advance the lifecycle generation before old async work can complete',
);
assert.match(
  source,
  /function\s+restorePage\s*\([^)]*\)\s*\{[\s\S]*retryRefresh\s*\(/,
  'bfcache restore must start a fresh recovery load rather than relying on pre-navigation requests',
);
assert.match(
  source,
  /async function loadPortfolio\s*\(generation\s*=\s*state\.lifecycleGeneration\)[\s\S]*if\s*\(!isCurrentGeneration\(generation\)\)\s*return/,
  'portfolio data arriving from an obsolete page generation must not write into the restored page',
);
assert.match(
  source,
  /async function refreshResearch\s*\([^)]*\)[\s\S]*const generation\s*=\s*state\.lifecycleGeneration[\s\S]*isCurrentGeneration\(generation\)/,
  'research result surfaces must ignore completions from an obsolete page generation',
);
