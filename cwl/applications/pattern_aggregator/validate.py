def _app_set(patterns):
    return set(patterns.get("wf_count", {}))


def validate_patterns(api_patterns, dag_patterns):
    api_wf = api_patterns.get("wf_count", {})
    dag_wf = dag_patterns.get("wf_count", {})
    api_apps = _app_set(api_patterns)
    dag_apps = _app_set(dag_patterns)

    api_only = {}
    dag_only = {}
    mismatch = {}

    for app in sorted(api_apps - dag_apps):
        api_only[app] = {"api_count": api_wf[app]["count"]}

    for app in sorted(dag_apps - api_apps):
        dag_only[app] = {"dag_count": dag_wf[app]["count"]}

    for app in sorted(api_apps & dag_apps):
        api_count = api_wf[app]["count"]
        dag_count = dag_wf[app]["count"]
        if api_count != dag_count:
            mismatch[app] = {
                "api_count": api_count,
                "dag_count": dag_count,
                "api_workflows": api_wf[app]["workflows"],
                "dag_workflows": dag_wf[app]["workflows"],
            }

    return {
        "summary": {
            "total_api_apps": len(api_wf),
            "total_dag_apps": len(dag_wf),
            "api_only_count": len(api_only),
            "dag_only_count": len(dag_only),
            "count_mismatch_count": len(mismatch),
        },
        "api_only": api_only,
        "dag_only": dag_only,
        "wf_count_mismatch": mismatch,
        "api_transitions_present": (
            sum(len(v) for v in api_patterns.get("transition_count", {}).values()) > 0
        ),
        "dag_transitions_present": (
            sum(len(v) for v in dag_patterns.get("transition_count", {}).values()) > 0
        ),
    }
