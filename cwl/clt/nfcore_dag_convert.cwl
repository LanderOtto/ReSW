class: CommandLineTool
cwlVersion: v1.2
label: Run nextflow preview, convert to graph JSON, optionally generate PNGs

baseCommand: [python3, -m, nfcore_toolkit, dag]

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  pipeline:
    type: string
    inputBinding:
      prefix: --pipeline
  profile:
    type: string?
    inputBinding:
      prefix: --profile
  nxf_home:
    type: string?
    default: /home/alberto/.nextflow
    label: Nextflow home directory (NXF_HOME) for pipeline cache
  syntax_parser:
    type: string?
    default: auto
    inputBinding:
      prefix: --syntax-parser
    label: NXF_SYNTAX_PARSER (auto, v1=groovy, v2=antlr4)
  generate_png:
    type: boolean?
    default: false
    inputBinding:
      prefix: --generate-png
  java17_home:
    type: string?
    inputBinding:
      prefix: --java17-home
  pipelines_json:
    type: File?
    inputBinding:
      prefix: --pipelines-json
  community:
    type: boolean?
    inputBinding:
      prefix: --community
    label: Community pipeline mode (skip nf-core API/module deps)

outputs:
  graph_json:
    type: File
    outputBinding:
      glob: "*_dir/*.graph.json"
  output_dir:
    type: Directory
    outputBinding:
      glob: "*_dir"

requirements:
  InlineJavascriptRequirement: {}
  EnvVarRequirement:
    envDef:
      PYTHONPATH: $(inputs.python_path)
      NXF_HOME: $(inputs.nxf_home)
  ResourceRequirement:
    ramMin: 1500