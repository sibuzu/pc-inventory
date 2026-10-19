import test from 'node:test';
import assert from 'node:assert/strict';
import {readRoute,routeHash,pageTabs} from '../dist/navigation.mjs';
const ids=['pc_china','pc_one','pc_andy'];
test('home opens comparison; old PC hashes and all tabs remain addressable',()=>{
  assert.equal(readRoute('/',ids).mode,'compare');
  assert.equal(readRoute('/#compare',ids).mode,'compare');
  assert.deepEqual(readRoute('/#pc_one',ids),{mode:'inventory',selected:'pc_one',tab:'overview'});
  for(const tab of pageTabs){const route={mode:'inventory',selected:'pc_andy',tab};assert.deepEqual(readRoute('/'+routeHash(route),ids),route);}
});
test('query links and upper-case hyphenated PC names resolve without changing stored IDs',()=>{
  const expected={mode:'inventory',selected:'pc_china',tab:'storage'};
  assert.deepEqual(readRoute('/?pc=PC-CHINA&tab=storage',ids),expected);
  assert.deepEqual(readRoute('/#PC-CHINA/STORAGE',ids),expected);
  assert.equal(readRoute('/?view=compare',ids).mode,'compare');
  assert.deepEqual(readRoute('/?view=compare#pc_china/storage',ids),expected);
});
test('unknown machines, malformed hash encoding and invalid tabs have safe fallbacks',()=>{
  assert.equal(readRoute('/#unknown/storage',ids).mode,'compare');
  assert.equal(readRoute('/#%E0%A4%A',ids).mode,'compare');
  assert.equal(readRoute('/#pc_one/unknown',ids).tab,'overview');
  assert.equal(readRoute('/?pc=pc_one&tab=unknown',ids).tab,'overview');
});
