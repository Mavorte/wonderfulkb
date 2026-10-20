# Metrics and Tags Reference

Read this reference before authoring definitions or re-evaluating historical data.

## Repository definitions

- Tags live at `tags/<slug>.json`.
- Metrics live at `metrics/<slug>.json`.

For a new tag, create the local starter before editing it:

```bash
wful scaffold tag needs-review --category Operations
```

The starter is manually applied, with LLM and deterministic evaluation disabled. Configure one evaluation approach only if the requested behavior needs it. Backoffice agents use runtime task tags and must use `wful tags backoffice` instead.

There is no metric scaffolder. Run `wful agents schema` before creating a metric or changing an existing tag or metric, and follow the generated schema. Keep each definition focused and name files with stable, descriptive slugs. A tag must use either LLM configuration or rule configuration, never both. A metric rule must have meaningful conditions.

## Runtime operations

Definitions are committed and validated with the agent repository. Re-evaluating historical activity and viewing metric results are runtime operations:

```bash
wful tags agent re-evaluate <agent> --tag <slug-or-id>
wful metrics agent re-evaluate <agent> --metric <id>
wful metrics agent stats <agent> --metric <id> --timeseries --days 30
```

Use a narrow historical re-evaluation only after the new definition has been validated and published. Inspect the resulting samples and metric statistics before widening the scope. Do not use runtime commands as a substitute for committing the definition that produced the result.
