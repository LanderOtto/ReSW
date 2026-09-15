import json
import os


def merge_graphs(input_dir, output_path):
    files = sorted(os.listdir(input_dir))
    graphs = []
    for fname in files:
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(input_dir, fname)
        with open(fpath) as f:
            graphs.append(json.load(f))
    manifest = {"graphs": graphs}
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
