const initialWorkflowNodes = [
{ id: 'schema_linker.yaml', targetFile: 'schema_linker.yaml', title: 'Schema Linker', category: 'Discovery', desc: 'Performs semantic candidate grounding for queries against live tables/columns.', tools: ['FQN Entity Matcher', 'Value-First Grounding Resolver'], x: 60, y: 40, color: 'border-blue
<truncated 1800 bytes>
0, color: 'border-amber-500/50 bg-amber-500/10 text-amber-400', icon: Repeat, isLoop: true }
];

// Compact U-Shape Topology: Down Left Column -> Bottom Bridge -> Up Right Column -> Loopback Feedback Bridge
const initialConnections = [
{ id: 'c1', from: 'schema_linker.yaml', to: 'table_pruner.yaml' },
{ id: 'c2', from: 'table_pruner.yaml', to: 'column_pruner.yaml' },
{ id: 'c3', from: 'column_pruner.yaml', to: 'sql_generator.yaml' },
{ id: 'c4', from: 'sql_generator.yaml', to: 'result_validator.yaml' },
{ id: 'c5', from: 'result_validator.yaml', to: 'self_corrector.yaml' },
{ id: 'c6', from: 'self_corrector.yaml', to: 'schema_linker.yaml', isFeedback: true }
];