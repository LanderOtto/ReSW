class: CommandLineTool
cwlVersion: v1.2
label: Merge multiple graph.json files into a single manifest.json

baseCommand: [python3, -m, nfcore_toolkit, merge-graphs]

requirements:
  InlineJavascriptRequirement: {}
  EnvVarRequirement:
    envDef:
      PYTHONPATH: $(inputs.python_path)
  InitialWorkDirRequirement:
    listing:
      - entryname: inputs
        entry:
          $(inputs.graph_files)

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  graph_files:
    type: File[]
    label: Array of .graph.json files to merge

arguments:
  - --input-dir
  - $(runtime.outdir)
  - --output
  - manifest.json

outputs:
  manifest:
    type: File
    outputBinding:
      glob: manifest.json
    label: Single manifest.json containing all embedded graph objects
