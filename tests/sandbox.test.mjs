import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluate } from '../collective101/execution/runner.mjs';

test('executes generated JavaScript and returns observed checks', async () => {
  const result = await evaluate({source:'function add(a,b){return a+b}',checks:[{expression:'add(2,3)',expected:5}]});
  assert.equal(result.passed,true);
  assert.equal(result.checks[0].actual,5);
});
test('wrong results fail independently of a claimed success', async () => {
  const result = await evaluate({source:'function add(){return 99}',checks:[{expression:'add(2,3)',expected:5}]});
  assert.equal(result.passed,false);
});
test('host filesystem, network, process and module APIs are absent', async () => {
  const result = await evaluate({source:'',checks:[{expression:"[typeof process,typeof require,typeof fetch,typeof WebSocket].join(',')",expected:'undefined,undefined,undefined,undefined'}]});
  assert.equal(result.passed,true);
});
test('infinite loops are interrupted', async () => {
  const start=Date.now();
  const result=await evaluate({source:'while(true){}',checks:[{expression:'true',expected:true}]});
  assert.equal(result.passed,false);
  assert.ok(Date.now()-start<3000);
});
test('memory exhaustion is contained', async () => {
  const result=await evaluate({source:'const arrays=[]; while(true) arrays.push(new Uint8Array(1024*1024));',checks:[{expression:'true',expected:true}]});
  assert.equal(result.passed,false);
});
test('syntax errors fail with execution evidence', async () => {
  const result=await evaluate({source:'function {',checks:[{expression:'true',expected:true}]});
  assert.equal(result.passed,false);
  assert.ok(result.checks[0].error);
});
test('each check gets a fresh runtime', async () => {
  const result=await evaluate({source:'let n=0; function inc(){return ++n}',checks:[{expression:'inc()',expected:1},{expression:'inc()',expected:1}]});
  assert.equal(result.passed,true);
});
test('unsupported outputs and excessive inputs fail closed', async () => {
  const result=await evaluate({source:'',checks:[{expression:'({})',expected:true}]});
  assert.equal(result.passed,false);
  await assert.rejects(evaluate({source:'x'.repeat(20001),checks:[]}));
});
