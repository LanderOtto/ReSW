# Design — pattern_aggregator

## Purpose
Build a Markov-1 transition model over application-labeled workflow graphs. Given a dataset of colored graphs, produce frequency tables for applications and their directed transitions. Provide a query tool to suggest likely next steps.

## Tool structure

```
applications/pattern_aggregator/
├── __init__.py
├── __main__.py
├── aggregator.py       # load graphs, count apps + transitions
├── query.py            # suggest next steps from patterns.json
└── validate.py         # compare API-derived vs DAG-derived patterns
```

## CLI

Three subcommands:

```
# Build the model from a manifest of graph objects (DAG branch)
python -m pattern_aggregator build manifest.json --output patterns_dag.json

# Build the model from an API pipeline listing (API branch)
python -m pattern_aggregator build --from-api pipelines.json --output patterns_api.json

# Query the model
python -m pattern_aggregator query \
  --patterns patterns.json --current bowtie2 --top 5

# Compare two patterns.json files (API-derived vs DAG-derived)
python -m pattern_aggregator validate \
  --api patterns_api.json --dag patterns_dag.json \
  --output validation.json
```

## Output format (`patterns.json`)

```json
{
  "total_workflows": 2,
  "wf_count": {
    "selectfirstdirectory": {
      "count": 2,
      "workflows": ["HBA_calibrator", "LBA_calibrator"]
    }
  },
  "transition_count": {
    "selectfirstdirectory": {
      "aoflag": {
        "count": 1,
        "workflows": ["HBA_calibrator"]
      }
    }
  }
}
```

## Counting rules

| Counter | Rule |
|---------|------|
| `wf_count[app]` | Number of workflows where `app` appears at least once |
| `transition_count[A][B]` | Total edges across all workflows (if A→B appears 3 times in one workflow, count = 3) |
| Workflow lists | Deduplicated — each `graph.id` appears at most once per key |

The workflow `id` comes from the colored graph's `graph.id` field (set by `dag_data_to_graph` on the DAG side, or `full_name` on the API side).

## Query output

```
$ python -m pattern_aggregator query \
    --patterns patterns.json --current gatk4.HaplotypeCaller --top 3

after gatk4.HaplotypeCaller (7 workflows):

  samtools sort      58%  (4 workflows)
  samtools index     25%  (2 workflows)
  gatk4.MergeVcfs    8%   (1 workflow)
```

- Percentage is `count(A→B) / count(A)` × 100
- The parenthetical is the raw workflow count for that transition
- Results sorted by count descending

## Validation output format (`validation.json`)

```json
{
  "summary": {
    "total_api_apps": 200,
    "total_dag_apps": 80,
    "api_only_count": 140,
    "dag_only_count": 20,
    "count_mismatch_count": 5
  },
  "api_only": {
    "fastqc": {"api_count": 40}
  },
  "dag_only": {
    "some_tool": {"dag_count": 3}
  },
  "wf_count_mismatch": {
    "bowtie2": {
      "api_count": 30,
      "dag_count": 8,
      "api_workflows": ["nf-core/rnaseq", ...],
      "dag_workflows": ["nf-core/rnaseq", ...]
    }
  },
  "api_transitions_present": false,
  "dag_transitions_present": true
}
```

- `api_only` — tools declared in API metadata but never observed in any DAG
- `dag_only` — tools observed in DAGs but absent from API metadata
- `wf_count_mismatch` — tools present in both sources but with different occurrence counts
- `api_transitions_present` / `dag_transitions_present` — sanity flags (API-derived graphs have no edges, so always `false`)

## Edge cases

| Case | Handling |
|------|----------|
| `app` is null (uncataloged step) | Skipped — no color to match on |
| Same app twice in one workflow | `wf_count` counts once per workflow; each edge counted per occurrence |
| No transitions for queried app | Show app frequency and note "no transitions recorded" |
| `--current` app not in patterns | Error with available apps list |
| Single graph with no transitions | `transition_count` empty, `wf_count` populated |
| Pipeline has no tools in API metadata | No nodes generated → workflow contributes no apps to patterns |
| No overlap between API and DAG apps | `api_only` and `dag_only` fully populated; `wf_count_mismatch` empty |
| Identical apps and counts | `summary` shows zero discrepancies; all sub-objects empty |

## Design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Order of Markov chain | 1 (immediate predecessor only) | Simpler to implement, less data-sparse. Higher orders can be added later. |
| Workflow reference lists | Keep full lists in this first implementation | Dataset is small now; can add truncation later if needed. |
| Subcommands | `build` / `query` / `validate` | Single entry point for all pattern-related operations. |
| `build --from-api` | Reads `pipelines.json` directly, no intermediate manifest | Eliminates an extra CWL step; API and DAG branches use the same `build` tool with different flags. |
| API graph ID convention | Uses raw `full_name` (e.g. `nf-core/rnaseq`) | Matches DAG convention — `validate` comparison works without normalization mismatch. |
| Validation output | Full structured JSON (not just text report) | Enables programmatic consumption by downstream tools or CI. |
| Validation scope | `wf_count` only (presence + count) | API metadata has no transition edges, so only app-level comparison is meaningful. |
