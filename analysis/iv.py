"""Reproduce the dark and illuminated current–voltage curves in report Fig. 14."""

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import linear_regression

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ("voltage_v", "current_a", "elapsed_time_s")
DISPLAY_WINDOW_V = (-0.90, 0.90)
# The first and last measured points visible in each original inset.
DARK_FIT_WINDOW_V = (-0.05, 0.15)
LIGHT_FIT_WINDOW_V = (-0.10, 0.20)


@dataclass(frozen=True)
class SweepPoint:
    voltage_v: float
    current_a: float
    elapsed_time_s: float


@dataclass(frozen=True)
class ResistanceFit:
    window_v: tuple[float, float]
    point_count: int
    slope_a_per_v: float
    intercept_a: float
    resistance_ohm: float
    r_squared: float


def load_sweep(path: Path) -> list[SweepPoint]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(COLUMNS).issubset(reader.fieldnames or ()):
            raise ValueError(f"{path}: expected columns {', '.join(COLUMNS)}.")
        points = []
        for row in reader:
            try:
                values = tuple(float(row[name]) for name in COLUMNS)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{reader.line_num}: invalid sweep value.") from error
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{path}:{reader.line_num}: non-finite sweep value.")
            points.append(SweepPoint(*values))
    if not points:
        raise ValueError(f"{path}: no sweep points.")
    return points


def window_points(points: list[SweepPoint], window_v: tuple[float, float]) -> list[SweepPoint]:
    low_v, high_v = window_v
    # Instrument exports represent nominal 50 mV steps as binary floats.
    tolerance_v = 1e-9
    return [
        point for point in points if low_v - tolerance_v <= point.voltage_v <= high_v + tolerance_v
    ]


def fit_resistance(points: list[SweepPoint], window_v: tuple[float, float]) -> ResistanceFit:
    selected = window_points(points, window_v)
    if len(selected) < 3 or len({point.voltage_v for point in selected}) < 2:
        raise ValueError(f"Fit window {window_v} V needs three points and at least two distinct voltages.")
    voltages = [point.voltage_v for point in selected]
    currents = [point.current_a for point in selected]
    slope, intercept = linear_regression(voltages, currents)
    if slope <= 0:
        raise ValueError(f"Fit window {window_v} V produced a nonpositive conductance.")
    average_current = sum(currents) / len(currents)
    residual_ss = sum(
        (current - (slope * voltage + intercept)) ** 2 for voltage, current in zip(voltages, currents)
    )
    total_ss = sum((current - average_current) ** 2 for current in currents)
    return ResistanceFit(window_v, len(selected), slope, intercept, 1 / slope, 1 - residual_ss / total_ss)


def write_sweep_data(
    sweeps: list[tuple[str, list[SweepPoint], ResistanceFit]], output: Path
) -> None:
    columns = ("condition", *COLUMNS, "plotted_in_figure", "used_in_fit", "fit_current_a")
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for condition, points, fit in sweeps:
            displayed = set(window_points(points, DISPLAY_WINDOW_V))
            fitted = set(window_points(points, fit.window_v))
            for point in points:
                used_in_fit = point in fitted
                writer.writerow({
                    "condition": condition,
                    **asdict(point),
                    "plotted_in_figure": point in displayed,
                    "used_in_fit": used_in_fit,
                    "fit_current_a": fit.slope_a_per_v * point.voltage_v + fit.intercept_a
                    if used_in_fit else "",
                })


def plot_sweeps(
    dark: list[SweepPoint],
    light: list[SweepPoint],
    dark_fit: ResistanceFit,
    light_fit: ResistanceFit,
    output: Path,
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.6, 4.45), layout="constrained")
    for axis, points, fit, name in zip(
        axes, (dark, light), (dark_fit, light_fit), ("(a) Dark", "(b) Illuminated")
    ):
        displayed = window_points(points, DISPLAY_WINDOW_V)
        axis.plot(
            [point.voltage_v for point in displayed],
            [point.current_a for point in displayed],
            "o--",
            color="tab:blue",
            markerfacecolor="none",
            markersize=4,
            label="Measured sweep",
        )
        axis.set_title(f"{name}  |  {fit.resistance_ohm / 1e6:.2f} MΩ")
        axis.set_xticks([-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75])
        axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        axis.legend(loc="upper left", frameon=False)

        zoom = axis.inset_axes([0.49, 0.11, 0.43, 0.32])
        fit_points = window_points(points, fit.window_v)
        fit_voltages = [point.voltage_v for point in fit_points]
        zoom.plot(
            fit_voltages, [point.current_a for point in fit_points], "o",
            color="tab:blue", markerfacecolor="none", markersize=4,
        )
        zoom.plot(
            fit_voltages, [fit.slope_a_per_v * voltage + fit.intercept_a for voltage in fit_voltages],
            color="tab:orange", label="Linear fit",
        )
        zoom.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        zoom.tick_params(labelsize=8)
        zoom.yaxis.get_offset_text().set_fontsize(8)
        zoom.legend(loc="upper left", frameon=False, fontsize=8)
        axis.indicate_inset_zoom(zoom, edgecolor="0.45", alpha=0.75)

    figure.supxlabel("Voltage (V)")
    figure.supylabel("Current (A)")
    figure.savefig(output, dpi=170)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data/raw")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "replicated")
    args = parser.parse_args()

    try:
        dark = load_sweep(args.input_dir / "iv_dark.csv")
        light = load_sweep(args.input_dir / "iv_light.csv")
        dark_fit = fit_resistance(dark, DARK_FIT_WINDOW_V)
        light_fit = fit_resistance(light, LIGHT_FIT_WINDOW_V)
        summary = {
            "method": "Ordinary least squares I = slope × V + intercept. R = 1 / slope.",
            "fit_window_source": "Voltage coordinates of measured points in the original Fig. 14 insets.",
            "display_window_v": DISPLAY_WINDOW_V,
            "dark_resistance_ohm": dark_fit.resistance_ohm,
            "illuminated_resistance_ohm": light_fit.resistance_ohm,
            "dark_to_illuminated_resistance_ratio": dark_fit.resistance_ohm / light_fit.resistance_ohm,
            "dark_fit": {"source_csv": "iv_dark.csv", "sweep_point_count": len(dark), **asdict(dark_fit)},
            "illuminated_fit": {
                "source_csv": "iv_light.csv", "sweep_point_count": len(light), **asdict(light_fit)
            },
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        plot_sweeps(dark, light, dark_fit, light_fit, args.output_dir / "current-voltage.png")
        write_sweep_data(
            [("dark", dark, dark_fit), ("illuminated", light, light_fit)],
            args.output_dir / "iv_recalculated.csv",
        )
        (args.output_dir / "iv_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(
        f"Dark resistance: {dark_fit.resistance_ohm / 1e6:.4f} MΩ. "
        f"Illuminated resistance: {light_fit.resistance_ohm / 1e6:.4f} MΩ."
    )


if __name__ == "__main__":
    main()
