import os

from hfmodel.model_io import load_fit_model


def _format_parameter_entry(param_set):
    fields = []
    name = param_set.get("name")
    if name:
        fields.append(name)
    if "n_parameters" in param_set:
        fields.append(f"n={param_set['n_parameters']}")
    if "inits" in param_set:
        fields.append(f"init={param_set['inits']}")
    if "bounds" in param_set:
        fields.append(f"bounds={param_set['bounds']}")
    if "fixed" in param_set:
        fields.append(f"fixed={param_set['fixed']}")
    return ", ".join(fields)


def load_and_summarize_model(model_file: str, verbose: int = 0):
    model_path = os.path.abspath(model_file)
    fit_model = load_fit_model(model_path)

    model = fit_model.model
    config = model.config

    channels = list(getattr(fit_model, "channels", []) or list(config.channels))
    process_names = list(getattr(fit_model, "process_names", []) or list(config.samples))
    observed_count = sum(float(v) for v in fit_model.observed_counts_by_channel.values())

    suggested_fixed = config.suggested_fixed() if callable(getattr(config, "suggested_fixed", None)) else getattr(config, "suggested_fixed", [])
    floating = len(config.par_order)
    if isinstance(suggested_fixed, (list, tuple)) and len(suggested_fixed) == len(config.par_order):
        floating = int(sum(0 if bool(flag) else 1 for flag in suggested_fixed))

    detail_lines = []
    if verbose:
        detail_lines.append("Parameter sets:")
        for parameter_set in config.par_map.values():
            detail_lines.append(f"  - {_format_parameter_entry(parameter_set)}")

    signal_processes = list(getattr(fit_model, "signal_processes", []))
    signal_text = ", ".join(signal_processes) if signal_processes else "none"

    return {
        "model_path": model_path,
        "model_name": "pyhf_workspace_model",
        "obs_range": "binned",
        "channels": channels,
        "processes": process_names,
        "signal_process": signal_text,
        "poi_name": getattr(fit_model, "poi_name", config.poi_name),
        "constraints": int(config.nauxdata),
        "floating_params": floating,
        "observed_count": observed_count,
        "pdf_lines": detail_lines,
    }
