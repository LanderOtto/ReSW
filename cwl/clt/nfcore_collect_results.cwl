class: CommandLineTool
cwlVersion: v1.2
label: Collect graph results into summary JSON

baseCommand: [python3, -m, nfcore_toolkit, collect]

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  manifest:
    type: File
    label: manifest.json with embedded graph objects
    inputBinding:
      position: 1

outputs:
  summary_json:
    type: File
    outputBinding:
      glob: summary.json
    label: Summary JSON with success/failure counts

arguments:
  - --summary-out
  - summary.json

requirements:
  InlineJavascriptRequirement: {}
  EnvVarRequirement:
    envDef:
      PYTHONPATH: $(inputs.python_path)
