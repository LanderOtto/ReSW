class: CommandLineTool
cwlVersion: v1.2
label: Build Markov-1 transition model from graph manifest or API listing

baseCommand: [python3, -m, pattern_aggregator, build]

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  input_file:
    type: File
    label: manifest.json or pipelines.json (depending on --from-api)
    inputBinding:
      position: 1
  from_api:
    type: boolean?
    label: Interpret input_file as pipelines.json from API listing
    inputBinding:
      prefix: --from-api
  output_name:
    type: string
    default: patterns.json
    inputBinding:
      prefix: --output

outputs:
  patterns_json:
    type: File
    outputBinding:
      glob: $(inputs.output_name)

requirements:
  InlineJavascriptRequirement: {}
  EnvVarRequirement:
    envDef:
      PYTHONPATH: $(inputs.python_path)
