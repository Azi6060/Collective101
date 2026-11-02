import { getQuickJS } from 'quickjs-emscripten';
import { pathToFileURL } from 'node:url';

const MEMORY = 16 * 1024 * 1024;
const DEADLINE_MS = 500;

export async function evaluate(input) {
  if (typeof input.source !== 'string' || input.source.length > 20000 || !Array.isArray(input.checks) || !input.checks.length || input.checks.length > 12) throw new Error('Invalid sandbox input');
  for (const check of input.checks) {
    if (typeof check.expression !== 'string' || !check.expression.trim() || check.expression.length > 2000 ||
        !['string','number','boolean'].includes(typeof check.expected) && check.expected !== null ||
        typeof check.expected === 'string' && check.expected.length > 4000 ||
        typeof check.expected === 'number' && !Number.isFinite(check.expected)) throw new Error('Checks require bounded expressions and primitive expected values');
  }
  const QuickJS = await getQuickJS();
  const start = Date.now();
  const checks = [];
  for (const check of input.checks) {
    const runtime = QuickJS.newRuntime();
    runtime.setMemoryLimit(MEMORY);
    runtime.setMaxStackSize(512 * 1024);
    runtime.setInterruptHandler(() => Date.now() - start > DEADLINE_MS);
    const vm = runtime.newContext();
    let actual = null;
    let error = null;
    try {
      const source = vm.evalCode(input.source, 'agent.js', {type:'global'});
      if (source.error) {
        source.error.dispose();
        error = 'Source failed: syntax/runtime error or resource limit';
      } else {
        source.value.dispose();
        const result = vm.evalCode(check.expression, 'acceptance-check.js', {type:'global'});
        if (result.error) {
          result.error.dispose();
          error = 'Check failed: evaluation error or resource limit';
        } else {
          try {
            const type = vm.typeof(result.value);
            if (type === 'number') actual = vm.getNumber(result.value);
            else if (type === 'string') {
              actual = vm.getString(result.value);
              if (actual.length > 4000) throw new Error('Result exceeds output limit');
            } else if (type === 'boolean' || vm.eq(result.value,vm.null)) actual = vm.dump(result.value);
            else throw new Error('Only primitive check results are supported');
          } finally { result.value.dispose(); }
        }
      }
    } catch (failure) { error = String(failure.message).slice(0,300); }
    finally { vm.dispose(); runtime.dispose(); }
    checks.push({expression:check.expression,expected:check.expected,actual,error,passed:!error && Object.is(actual,check.expected)});
  }
  return {engine:'QuickJS/WebAssembly',passed:checks.every(c=>c.passed),checks,duration_ms:Date.now()-start,
    limits:{memory_bytes:MEMORY,deadline_ms:DEADLINE_MS,host_apis:false}};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let source='';
  try {
    for await (const chunk of process.stdin) {
      source+=chunk;
      if(source.length>100000) throw new Error('Input exceeds 100 KB');
    }
    process.stdout.write(JSON.stringify(await evaluate(JSON.parse(source))));
  } catch(error) {
    process.stdout.write(JSON.stringify({engine:'QuickJS/WebAssembly',passed:false,checks:[],error:String(error.message).slice(0,300)}));
    process.exitCode=1;
  }
}
