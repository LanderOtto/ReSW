class: CommandLineTool
cwlVersion: v1.2
label: List all nf-core pipelines with their tools

baseCommand: [python3, -m, nfcore_toolkit, list]

arguments:
  - --json
  - --select-out
  - selected_pipelines.txt

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  filter:
    type: string?
    inputBinding:
      prefix: --filter
  include_archived:
    type: boolean?
    inputBinding:
      prefix: --all
  include_unreleased:
    type: boolean?
    inputBinding:
      prefix: --include-unreleased
  max_count:
    type: int?
    label: Max pipelines to select for DAG extraction (0 = none)
    inputBinding:
      prefix: --max

outputs:
  pipelines_json:
    type: File
    outputBinding:
      glob: pipelines.json
    label: JSON array of all pipelines with tool metadata
  pipeline_names:
    type: string[]
    outputBinding:
      glob: selected_pipelines.txt
      loadContents: true
      outputEval: $(self[0].contents.trim().split('\n'))
    label: Selected pipeline names (one per line)

requirements:
  InlineJavascriptRequirement: {}
  EnvVarRequirement:
    envDef:
      PYTHONPATH: $(inputs.python_path)

stdout: pipelines.json
