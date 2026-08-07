import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../../app/web/app.js', import.meta.url), 'utf8');

assert.match(
  source,
  /researchInterrupted:\s*false/,
  'lifecycle state must track whether navigation interrupted an in-flight research action',
);
assert.match(
  source,
  /state\.researchInterrupted\s*=\s*Boolean\(state\.researchPromise\)/,
  'page suspension must remember an interrupted research action before invalidating its promise',
);
assert.match(
  source,
  /采集已中断，可重试。/,
  'bfcache restore must expose an explicit recoverable result for interrupted research',
);
assert.match(
  source,
  /researchButton\.disabled\s*=\s*!runtime\.capabilities\.researchRefresh/,
  'restore must return the primary research control to its capability-defined state',
);
assert.match(
  source,
  /researchRetryButton\.disabled\s*=\s*false/,
  'restore must make research retry actionable after an interrupted request',
);
