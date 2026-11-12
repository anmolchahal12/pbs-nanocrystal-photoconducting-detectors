"""Analyze PbS particle diameters and electron-diffraction peak widths."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from itertools import groupby
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTED_DATA = PROJECT_ROOT / "data" / "reported"
SCHERRER_SHAPE_FACTOR = 0.89
TEAL = "#146f67"
BLUE = "#365c80"
INK = "#18313f"
GRID = "#dfe6ea"


def positive_number(value: str | float | None, description: str) -> float:
    try:
        number = float(value) if value is not None else math.nan
    except ValueError as error:
        raise ValueError(f"{description} must be a positive number") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{description} must be a finite positive number")
    return number


def read_reported_results() -> dict:
    """Read the transcribed values and recalculate lengths from rounded FWHM."""
    with (REPORTED_DATA / "tem_summary.csv").open(newline="", encoding="utf-8") as file:
        fields = [
            {
                "field": row["field"],
                "mean_diameter_nm": float(row["mean_diameter_nm"]),
                "sd_diameter_nm": float(row["sd_diameter_nm"]),
            }
            for row in csv.DictReader(file)
        ]

    with (REPORTED_DATA / "scherrer_peaks.csv").open(newline="", encoding="utf-8") as file:
        peaks = []
        for row in csv.DictReader(file):
            width = positive_number(row["fwhm_nm_inverse"], "Fitted peak width")
            peaks.append(
                {
                    "angle_deg": int(row["angle_deg"]),
                    "reflection": row["reflection"],
                    "fwhm_nm_inverse": width,
                    "reported_length_nm": float(row["reported_length_nm"]),
                    "recalculated_length_nm": SCHERRER_SHAPE_FACTOR / width,
                }
            )

    return {
        "tem_reported_diameter_summaries": fields,
        "scherrer": {
            "shape_factor": SCHERRER_SHAPE_FACTOR,
            "reported_mean_length_nm": statistics.mean(
                peak["reported_length_nm"] for peak in peaks
            ),
            "recalculated_mean_length_nm": statistics.mean(
                peak["recalculated_length_nm"] for peak in peaks
            ),
            "peaks": peaks,
        },
    }


def read_particle_areas(
    paths: list[Path],
    area_column: str,
    area_unit: str,
    nm_per_pixel: float | None,
) -> list[dict]:
    """Convert projected areas to area-equivalent circular diameters."""
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("each particle CSV must be supplied only once")
    length_scale = nm_per_pixel if area_unit == "px2" else 1.0
    if length_scale is None:
        raise ValueError("pixel areas require an nm-per-pixel calibration")

    particles = []
    for field_index, path in enumerate(paths, start=1):
        with path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if area_column not in (reader.fieldnames or []):
                raise ValueError(f"{path} has no column named {area_column!r}")
            starting_count = len(particles)
            for row in reader:
                area = positive_number(
                    row[area_column], f"{path}:{reader.line_num} {area_column!r}"
                )
                diameter = 2.0 * math.sqrt(area / math.pi) * length_scale
                if not math.isfinite(diameter) or diameter <= 0:
                    raise ValueError(f"{path}:{reader.line_num} diameter is out of range")
                particles.append(
                    {
                        "field": f"Field {field_index}",
                        "source_file": path.name,
                        "area": area,
                        "area_unit": area_unit,
                        "equivalent_diameter_nm": diameter,
                    }
                )
            if len(particles) == starting_count:
                raise ValueError(f"{path} contains no particle areas")
    return particles


def particle_statistics(particles: list[dict]) -> dict:
    diameters = [particle["equivalent_diameter_nm"] for particle in particles]
    return {
        "count": len(diameters),
        "mean_diameter_nm": statistics.mean(diameters),
        "median_diameter_nm": statistics.median(diameters),
        "sample_sd_nm": statistics.stdev(diameters) if len(diameters) > 1 else None,
    }


def new_plot(title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(6.4, 3.8), layout="constrained")
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.set_axisbelow(True)
    ax.spines[["right", "top"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    return fig, ax


def save_plot(fig, path: Path) -> None:
    fig.savefig(path, dpi=240, facecolor="white")
    plt.close(fig)


def plot_reported_tem(fields: list[dict], path: Path) -> None:
    fig, ax = new_plot(
        "HAADF-STEM particle diameters", "Image field", "Diameter (nm)"
    )
    ax.errorbar(
        [field["field"] for field in fields],
        [field["mean_diameter_nm"] for field in fields],
        yerr=[field["sd_diameter_nm"] for field in fields],
        fmt="o",
        color=TEAL,
        markersize=7,
        capsize=5,
        label="Mean ± standard deviation",
    )
    ax.set_xlim(-0.5, len(fields) - 0.5)
    ax.legend(frameon=False)
    save_plot(fig, path)


def plot_scherrer(scherrer: dict, path: Path) -> None:
    fig, ax = new_plot(
        "Scherrer coherent-domain lengths", "Line profile and reflection", "Length (nm)"
    )
    peaks = scherrer["peaks"]
    positions = range(len(peaks))
    ax.scatter(
        positions, [p["recalculated_length_nm"] for p in peaks], color=TEAL,
        s=54, label="Coherent-domain length", zorder=3,
    )
    mean_length = scherrer["recalculated_mean_length_nm"]
    ax.axhline(
        mean_length, color=BLUE, linestyle="--",
        linewidth=1, label=f"Mean ({mean_length:.2f} nm)",
    )
    ax.set_xticks(
        positions, [f"{p['angle_deg']}°\n{p['reflection']}" for p in peaks]
    )
    ax.legend(frameon=False, fontsize=8)
    save_plot(fig, path)


def write_particle_outputs(particles: list[dict], out_dir: Path) -> None:
    diameter_column = "equivalent_diameter_nm"
    fig, ax = new_plot(
        "TEM particle-size distribution", "Area-equivalent diameter (nm)", "Count"
    )
    ax.hist(
        [particle[diameter_column] for particle in particles],
        bins="auto",
        color=TEAL,
        edgecolor="white",
    )
    ax.text(
        0.98, 0.95, f"n = {len(particles)}", transform=ax.transAxes,
        ha="right", va="top", color=INK,
    )
    save_plot(fig, out_dir / "tem_particle_distribution.png")
    with (out_dir / "tem_particle_diameters.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=["field", "source_file", "area", "area_unit", diameter_column]
        )
        writer.writeheader()
        writer.writerows(particles)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument(
        "--particles-csv", type=Path, action="append", default=[],
        help="ImageJ area export. Repeat once per field to pool the particle measurements.",
    )
    parser.add_argument("--area-column", default="Area")
    parser.add_argument("--area-unit", choices=["nm2", "px2"])
    parser.add_argument(
        "--nm-per-pixel", type=float, help="Shared calibration for all supplied pixel areas."
    )
    args = parser.parse_args()

    if args.particles_csv and not args.area_unit:
        parser.error("--particles-csv requires --area-unit nm2 or px2")
    if not args.particles_csv and (args.area_unit or args.nm_per_pixel is not None):
        parser.error("area units and calibration require --particles-csv")
    if args.nm_per_pixel is not None and args.area_unit != "px2":
        parser.error("--nm-per-pixel applies only to --area-unit px2")

    try:
        scale = (
            positive_number(args.nm_per_pixel, "--nm-per-pixel")
            if args.nm_per_pixel is not None else None
        )
        particles = read_particle_areas(
            args.particles_csv, args.area_column, args.area_unit, scale
        ) if args.particles_csv else []
        summary = read_reported_results()
        if particles:
            summary["tem_particle_csv_analysis"] = {
                "area_unit": args.area_unit,
                "nm_per_pixel": scale,
                "pooled": particle_statistics(particles),
                "fields": [
                    {"field": field, "source_file": filename, **particle_statistics(list(rows))}
                    for (field, filename), rows in groupby(
                        particles, key=lambda row: (row["field"], row["source_file"])
                    )
                ],
            }
        args.out_dir.mkdir(parents=True, exist_ok=True)
        plot_reported_tem(
            summary["tem_reported_diameter_summaries"],
            args.out_dir / "tem_reported_summary.png",
        )
        plot_scherrer(summary["scherrer"], args.out_dir / "scherrer_comparison.png")
        if particles:
            write_particle_outputs(particles, args.out_dir)
        with (args.out_dir / "microscopy_summary.json").open("w", encoding="utf-8") as file:
            json.dump(summary, file, indent=2, allow_nan=False)
            file.write("\n")
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")

    print(f"Microscopy results written to {args.out_dir}")


if __name__ == "__main__":
    main()
