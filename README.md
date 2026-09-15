# ReSW: Reusability in Scientific Workflows

Curated workflow catalogs are central to modern scientific computing, yet the reuse of existing components remains surprisingly limited. This challenge is further amplified by AI coding assistants, which frequently generate custom logic from scratch because their optimization objectives do not explicitly reward component reuse. 
This work introduces a unified framework for evaluating, recommending, and adapting reusable workflow components for both human developers and AI agents. At its core is the Missed Reuse Score (MRS), a novel metric that estimates the extent to which a workflow step represents a missed opportunity to reuse an existing catalog component.

## Prerequisites and Installation

**Requirements:**
- Python 3.x (Replace with your specific version, e.g., 3.10+)
- Nextflow v26.04.4 or higher
- Docker or Node.js (Required because the project includes CWL workflows)

**Setup:**
Clone the repository and set up a virtual environment:

```bash
python -m venv venv 
source venv/bin/activate 
pip install -r requirements.txt
```

## Analysis of nf-core Modules and the nxf Community

**How to run**
To execute the community analysis and plot the results, run the following commands:

```bash
python -m nfx_community analyze --limit 550 
python -m nfx_community plot
```

**Results**
This will generate the `nextflow_analysis.json` file, which contains an analysis of every pipeline, as well as a `plots` directory containing various plots based on the analysis results regarding pipelines, module usage, and MRS scores.

## Analysis of the nf-core Catalog

This analysis is defined as a CWL workflow. It retrieves and analyzes the workflows in the nf-core catalog, which are officially maintained by the nf-core community.

**How to run**
Before running, adjust the parameters (in particular, the file paths) in the cwl/config_nfcore.yml file.
Then, execute the workflow using your CWL runner:

```bash
cwl-runner cwl/workflows/nfcore_workflow.cwl cwl/config_nfcore.yml
```

**Results**
The workflow runs multiple analyses regarding the most common subworkflows across different main workflows. It produces multiple outputs:

- `analysis_plots/`: Directory containing the visual results of the workflow analysis.
- `analysis_report_full/`: Directory containing detailed text files about the results (contains more raw data compared to the plotted versions).
- `[ORGANIZATION].[WORKFLOW_NAME]_dir/`: Directories containing specific workflow information in three formats (two graphical formats and one JSON).
- `analysis_report_summary.txt`: A short overview of all the results contained in the full report directory.
- `patterns_api.json`
- `patterns_dag.json`
- `pipelines.json`: Contains all the raw workflow information.
- `summary.json`: Contains a summary of the analysis execution, including any failures during phases such as retrieval or parsing.