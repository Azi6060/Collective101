// Stand-in derived from https://dev.meta.ai/docs/tool-calling, not an owner's mock.
// Explicitly exercises protocol behavior; it cannot establish model quality.
const http = require('http');
const definitions = [
  ['profile', 'Inspect event records', 'research', [], 'profile_dataset', 'dataset_inspection', 'profile'],
  ['attendance', 'Calculate historical attendance', 'data', [], 'analyze_attendance', 'attendance_analysis', 'attendance'],
  ['budget', 'Build operating plan', 'operations', ['attendance'], 'build_event_plan', 'event_planning', 'budget'],
  ['brief', 'Draft event brief', 'communications', ['profile', 'attendance', 'budget'], 'draft_event_brief', 'brief_generation', 'brief'],
  ['delivery', 'Assemble deliverables', 'strategy', ['profile', 'attendance', 'budget', 'brief'], 'assemble_report', 'report_assembly', 'report'],
];
function reply(res, status, value) {
  res.writeHead(status, {'content-type': 'application/json'});
  res.end(JSON.stringify(value));
}
http.createServer((req, res) => {
  if (req.method !== 'POST' || req.url.split('?')[0] !== '/v1/chat/completions') {
    return reply(res, 501, {error: {message: 'Endpoint outside the modeled contract'}});
  }
  // Postman interceptRequests supplies req.body; the fallback also permits a local Node run.
  function handle(body) {
    try {
      if (!body || typeof body.model !== 'string' || !Array.isArray(body.messages) || body.max_tokens !== 4096) {
        return reply(res, 400, {error: {message: 'Invalid model request contract'}});
      }
      const context = JSON.parse(body.messages[1].content);
      let message;
      if (context.phase === 'invalid_json') {
        res.writeHead(200, {'content-type': 'application/json'}); return res.end('this is not JSON');
      }
      if (context.phase === 'truncated') {
        return reply(res, 200, {choices: [{message: {role:'assistant', content:'{"partial":'}, finish_reason:'length'}], usage:{total_tokens: 15}});
      }
      if (context.phase === 'plan') {
        const tasks = definitions.map(([key, title, department, depends_on, tool, capability, check]) => ({
          key, title, department, depends_on, tool, capability, check,
          instruction: 'Use the assigned local tool and cite real evidence; expose limitations.'
        }));
        message = {role:'assistant', content:JSON.stringify({tasks})};
      } else if (context.phase === 'review') {
        message = {role:'assistant', content:JSON.stringify({accepted:true, reason:'Contract stand-in verdict; local checks remain authoritative.'})};
      } else if (context.phase === 'execute') {
        const outputs = body.messages.filter(item => item.role === 'tool').map(item => JSON.parse(item.content));
        const grants = outputs.filter(item => item.granted);
        const evidence = outputs.filter(item => item.evidence_id);
        if (!body.tools?.every(tool => tool.type === 'function' && tool.function?.parameters?.type === 'object')) {
          return reply(res, 400, {error:{message:'Expected nested Chat Completions tool schemas'}});
        }
        if (evidence.length) {
          message = {role:'assistant', content:JSON.stringify({summary:'HTTP contract stand-in execution', evidence_ids:evidence.map(item => item.evidence_id)})};
        } else {
          const name = grants.length ? context.task.tool : 'request_capability';
          const args = grants.length ? {} : {capability: context.task.capability};
          if (!body.tools.some(tool => tool.function.name === name)) {
            return reply(res, 400, {error:{message:'Requested function was not exposed'}});
          }
          message = {role:'assistant', content:null, tool_calls:[{id:'call_' + outputs.length, type:'function', function:{name, arguments:JSON.stringify(args)}}]};
        }
      } else {
        return reply(res, 400, {error:{message:'Unknown contract test phase'}});
      }
      return reply(res, 200, {id:'chatcmpl-contract', object:'chat.completion', choices:[{index:0, message, finish_reason:message.tool_calls ? 'tool_calls' : 'stop'}], usage:{prompt_tokens:10, completion_tokens:10, total_tokens:20}});
    } catch (_) { return reply(res, 400, {error:{message:'Invalid request JSON or conversation'}}); }
  }
  if (req.body !== undefined) return handle(req.body);
  let chunks = '';
  req.on('data', chunk => { chunks += chunk; });
  req.on('end', () => { try { handle(JSON.parse(chunks)); } catch (_) { reply(res,400,{error:{message:'Invalid JSON'}}); } });
}).listen(process.env.PORT || 4011);
