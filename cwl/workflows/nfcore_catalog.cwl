class: Workflow
cwlVersion: v1.2
label: nf-core pipeline analyzer — list → DAG → patterns

requirements:
  InlineJavascriptRequirement: {}
  ScatterFeatureRequirement: {}

inputs:
  python_path:
    type: Directory
    label: PYTHONPATH (applications dir)
  filter_keyword:
    type: string?
    label: Optional keyword to filter pipelines (by name, description, topics)
  max_pipelines:
    type: int?
    label: Max pipelines to run DAG extraction on (0 = skip DAG, only list)
  profile:
    type: string?
    default: test
    label: Nextflow profile (test / full / staging)
  nxf_home:
    type: string?
    default: /home/alberto/.nextflow
    label: Nextflow home directory for pipeline cache
  syntax_parser:
    type: string?
    default: auto
    label: NXF_SYNTAX_PARSER (auto, v1=groovy, v2=antlr4)
  generate_png:
    type: boolean?
    default: false
    label: Generate PNG visualizations from DOT and graph JSON
  java17_home:
    type: string?
    label: JAVA_HOME for Java 17 (required for DSL1 rollback)
  cores:
    type: int?
    default: 1
    label: Parallel worker processes for plot generation
  include_archived:
    type: boolean?
    default: false 
    label: Include in the analysis nfcore archived pipelines 
  include_unreleased:
    type: boolean?
    default: false 
    label: Include unreleased pipelines in the analysis (latest_release=='dev')
  plot_font_file:
    type: File?
outputs:
  pipelines_index:
    type: File
    outputSource: list_pipelines/pipelines_json
    label: Full pipeline index with tool metadata from nf-core API
  graphs_dir:
    type: Directory[]
    outputSource: dag_convert/output_dir
    label: Per-pipeline subdirs with graph.json + dag.png + graph.png
  summary:
    type: File
    outputSource: collect/summary_json
    label: Summary JSON with success/failure counts
  patterns_api:
    type: File
    outputSource: build_api_patterns/patterns_json
    label: Markov-1 transition model built from API-declared tools
  patterns_dag:
    type: File
    outputSource: build_dag_patterns/patterns_json
    label: Markov-1 transition model built from DAG-observed tools and edges
  analysis_report_summary:
    type: File
    outputSource: analyze_patterns/analysis_report_summary
    label: Cross-pipeline pattern analysis summary
  analysis_report_full:
    type: Directory
    outputSource: analyze_patterns/analysis_report_full
    label: Cross-pipeline pattern analysis full report
  analysis_plots:
    type: Directory?
    outputSource: analyze_patterns/plots
    label: Generated plots (tool popularity, transitions, topology, domains)

steps:

  pythonpath:
    run:
      class: ExpressionTool 
      inputs:
        file: Directory 
      outputs:
        str: string 
      expression: $(inputs.file.path)
    in:
      file: python_path 
    out: [str]

  list_pipelines:
    run: ../clt/nfcore_list_pipelines.cwl
    in:
      python_path: pythonpath/str
      filter: filter_keyword
      max_count: max_pipelines
      include_archived: include_archived
      include_unreleased: include_unreleased
    out: [pipelines_json, pipeline_names]
    label: Fetch all nf-core pipelines from API, optionally select subset

  dag_convert:
    run: ../clt/nfcore_dag_convert.cwl
    in:
      python_path: pythonpath/str
      pipeline: list_pipelines/pipeline_names
      profile: profile
      nxf_home: nxf_home
      syntax_parser: syntax_parser
      generate_png: generate_png
      java17_home: java17_home
      pipelines_json: list_pipelines/pipelines_json
    scatter:
      - pipeline
    scatterMethod: dotproduct
    out: [graph_json, output_dir]
    label: Run nextflow preview, convert to graph JSON, optionally generate PNGs

  collect:
    run: ../clt/nfcore_collect_results.cwl
    in:
      python_path: pythonpath/str
      manifest: merge_graphs/manifest
    out: [summary_json]
    label: Collect results into summary JSON

  merge_graphs:
    run: ../clt/nfcore_merge_graphs.cwl
    in:
      python_path: pythonpath/str
      graph_files: dag_convert/graph_json
    out: [manifest]
    label: Merge DAG graph files into single manifest

  build_api_patterns:
    run: ../clt/nfcore_build_patterns.cwl
    in:
      python_path: pythonpath/str
      input_file: list_pipelines/pipelines_json
      from_api:
        default: true
      output_name:
        default: patterns_api.json
    out: [patterns_json]
    label: Build Markov-1 transition model from API-declared tools

  build_dag_patterns:
    run: ../clt/nfcore_build_patterns.cwl
    in:
      python_path: pythonpath/str
      input_file: merge_graphs/manifest
      output_name:
        default: patterns_dag.json
    out: [patterns_json]
    label: Build Markov-1 transition model from DAG-observed tools and edges

  analyze_patterns:
    run: ../clt/nfcore_analyze_patterns.cwl
    in:
      python_path: pythonpath/str
      graph_files: dag_convert/graph_json
      patterns_dag: build_dag_patterns/patterns_json
      cores: cores
      plot_font_file: plot_font_file
    out: [analysis_report_summary, analysis_report_full, plots]
    label: Cross-pipeline pattern analysis (co-occurrence, topology, domains)
