import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow = JSON.parse(fs.readFileSync('integrations/n8n/folklore-variant-interpretation.json'));
const expression = workflow.nodes.find(n => n.name === 'Folklore MCP interpretation').parameters.body;
const invoke = new Function('$json', `return ${expression.slice(3, -3)};`);
const user = '77e8885e-02a4-43ca-a63a-20fcdcd65d94';
const session = '7f78d2e5-12e1-4142-86b5-cf872731420e';
const settings = {variant: 'rs80357914', analytics_opt_in: true, analytics_user_id: user,
  analytics_session_id: session, analytics_intent: 'variant_evidence', reason: 'private', email: 'private'};
const call = values => JSON.parse(invoke(values)).params;
const valid = call(settings);
assert.deepEqual(valid.arguments, {assembly: 'GRCh38', query: 'rs80357914'});
assert.deepEqual(valid._meta['io.helena/analytics'], {opt_in: true, user_id: user, session_id: session, intent: 'variant_evidence'});
assert.equal(valid._meta['io.modelcontextprotocol/protocolVersion'], '2026-07-28');
for (const change of [
  {analytics_opt_in: false}, {analytics_opt_in: 'true'}, {analytics_opt_in: 1},
  {analytics_user_id: 'patient@example.invalid'}, {analytics_user_id: user.toUpperCase()},
  {analytics_user_id: []}, {analytics_user_id: user.replace('-43ca-', '-13ca-')},
]) {
  assert.equal(call({...settings, ...change})._meta['io.helena/analytics'], undefined);
}
assert.equal(call({variant: 'rs80357914'})._meta['io.helena/analytics'], undefined);
assert.deepEqual(call({...settings, analytics_session_id: 'private', analytics_intent: 'private'})
  ._meta['io.helena/analytics'], {opt_in: true, user_id: user});
const second = 'f29fe568-bd51-465e-8b13-eb20a8112ac9';
assert.equal(call({...settings, analytics_session_id: second})._meta['io.helena/analytics'].session_id, second);
assert.equal(call(settings)._meta['io.helena/analytics'].session_id, session);
assert.equal(workflow.nodes.find(n => n.name === 'Variant query').parameters.assignments.assignments
  .find(a => a.name === 'analytics_opt_in').value, false);
console.log('n8n request expression: anonymous, opt-in, opt-out, validation and session separation PASS');
