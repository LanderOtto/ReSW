import matplotlib.pyplot as plt

from ._colors import C_EXACT, C_MID


def plot_script_interpreters(data, output_dir, name, **kargs):
    """Two-panel bar chart: process script interpreters, community vs nf-core.

    Reads ``module_analysis.script_interpreters = {community, nfcore}``.
    The ``default`` bucket (no ``#!`` shebang) is reported in the panel titles
    so the declared-interpreter bars remain readable.
    """
    si = (data.get("module_analysis", {}) or {}).get("script_interpreters") or {}
    comm = dict(si.get("community") or {})
    nfcore = dict(si.get("nfcore") or {})
    if not comm and not nfcore:
        print("    No script interpreter data to plot.")
        return

    comm_default = comm.pop("default", 0)
    nfcore_default = nfcore.pop("default", 0)

    keys = sorted(
        set(comm) | set(nfcore),
        key=lambda k: -(comm.get(k, 0) + nfcore.get(k, 0)),
    )
    if not keys:
        print("    No declared interpreters to plot.")
        return

    comm_vals = [comm.get(k, 0) for k in keys]
    nfcore_vals = [nfcore.get(k, 0) for k in keys]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 0.45 * len(keys) + 1.4))

    y = list(range(len(keys)))
    panels = [
        (ax1, comm_vals, C_EXACT, "Community", comm_default),
        (ax2, nfcore_vals, C_MID, "nf-core", nfcore_default),
    ]
    for ax, vals, color, title, dflt in panels:
        ax.barh(y, vals, color=color, edgecolor="white", height=0.7)
        ax.set_yticks(y)
        ax.set_yticklabels(keys, fontsize=11)
        ax.invert_yaxis()
        ax.set_xlabel("processes")
        ax.set_title(f"{title} (default/no shebang: {dflt})", fontsize=12)
        for yi, v in zip(y, vals):
            if v:
                ax.text(v, yi, f" {v}", va="center", fontsize=10)
        ax.set_ylim(-0.6, len(keys) - 0.4)

    fig.suptitle(
        "Process script interpreters (declared #!)", fontsize=13, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - community {sum(comm_vals) + comm_default} "
        f"({comm_default} default), nf-core {sum(nfcore_vals) + nfcore_default} "
        f"({nfcore_default} default)"
    )
