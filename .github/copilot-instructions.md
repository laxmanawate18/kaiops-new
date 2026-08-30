# Context Optimization & Token-Saving Protocol

- Before doing broad file searches or grepping across the repository, read `graphify-out/GRAPH_REPORT.md` to identify structural entry points and high-degree "god nodes".
- Query focused subgraphs using `graphify query "<feature or relation>"` or inspect `graphify-out/graph.json` rather than pulling raw source files into context.
- Avoid loading entire directories into the prompt; read only the targeted files identified by the dependency graph.

