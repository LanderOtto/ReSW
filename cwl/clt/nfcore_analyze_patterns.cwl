class: CommandLineTool
cwlVersion: v1.2
label: Analyze cross-pipeline patterns — tool co-occurrence, topology, domain clusters

baseCommand: [python3, -m, nfcore_toolkit, analyze-patterns]

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
  ResourceRequirement:
    coresMin: $(inputs.cores)
    ramMin: 256

arguments:
  - --input-dir
  - $(runtime.outdir)

inputs:
  python_path:
    type: string
    label: PYTHONPATH value (set via EnvVarRequirement)
  graph_files:
    type: File[]
    label: All per-pipeline graph.json files
  patterns_dag:
    type: File
    inputBinding:
      prefix: --patterns-dag
    label: patterns_dag.json from pattern_aggregator
  output:
    type: string?
    default: analysis_report_summary.txt
    inputBinding:
      prefix: --output
    label: Summary report filename
  plot_dir:
    type: string?
    default: analysis_plots
    inputBinding:
      prefix: --plot-dir
    label: Directory for generated plots
  cores:
    type: int?
    default: 1
    inputBinding:
      prefix: --cores
    label: Parallel worker processes for plots
  plot_font_file:
    type: File?
    default: null
    inputBinding:
      prefix: --font-path
    label: Font file for the plots

outputs:
  analysis_report_summary:
    type: File
    outputBinding:
      glob: analysis_report_summary.txt
  analysis_report_full:
    type: Directory
    outputBinding:
      glob: analysis_report_full
  plots:
    type: Directory?
    outputBinding:
      glob: analysis_plots
