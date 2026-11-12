"""Analyze the optical absorbance of PbS nanocrystals."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "absorbance.csv"
HC_EV_NM = 1239.841984
COLUMNS = (
    "wavelength_nm",
    "sample_counts",
    "dark_counts",
    "reference_counts",
    "exported_absorbance_au",
)
MOREELS_BULK_GAP_EV = 0.41
MOREELS_QUADRATIC = 0.0252
MOREELS_LINEAR = 0.283
MOREELS_DIAMETER_RANGE_NM = (3.9, 13.3)
# Estimated first-exciton interval at the long-wavelength limit.
FIRST_EXCITON_RANGE_NM = (1750.0, 1800.0)
# Mark the two longest-wavelength samples separately in the plotted scan.
SOLID_TRACE_LAST_WAVELENGTH_NM = 1757.72


@dataclass(frozen=True)
class AbsorbancePoint:
    wavelength_nm: float
    sample_counts: float
    dark_counts: float
    reference_counts: float
    exported_absorbance_au: float

    @property
    def energy_ev(self) -> float:
        return HC_EV_NM / self.wavelength_nm

    @property
    def calculated_absorbance_au(self) -> float:
        return math.log10(
            (self.reference_counts - self.dark_counts)
            / (self.sample_counts - self.dark_counts)
        )


def read_spectrum(path: Path) -> list[AbsorbancePoint]:
    points = []
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not set(COLUMNS).issubset(reader.fieldnames or ()):
            raise ValueError(f"expected CSV columns: {', '.join(COLUMNS)}")
        for row in reader:
            try:
                values = [float(row[column]) for column in COLUMNS]
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path.name}:{reader.line_num}: invalid number") from error
            point = AbsorbancePoint(*values)
            if not all(math.isfinite(value) for value in values) or point.wavelength_nm <= 0:
                raise ValueError(f"{path.name}:{reader.line_num}: invalid wavelength or counts")
            if min(point.sample_counts, point.reference_counts) <= point.dark_counts:
                raise ValueError(f"{path.name}:{reader.line_num}: nonpositive dark-corrected counts")
            points.append(point)
    if len(points) < 3 or len({point.wavelength_nm for point in points}) != len(points):
        raise ValueError("expected at least three distinct wavelengths")
    return sorted(points, key=lambda point: point.wavelength_nm)


def moreels_diameter_nm(first_exciton_ev: float) -> float:
    """Invert Moreels et al., ACS Nano 3 (2009), p. 3024, Eq. (1)."""
    if not math.isfinite(first_exciton_ev) or first_exciton_ev <= MOREELS_BULK_GAP_EV:
        raise ValueError("first-exciton energy must be above the bulk PbS gap of 0.41 eV")
    inverse_gap_shift = 1 / (first_exciton_ev - MOREELS_BULK_GAP_EV)
    return (2 * inverse_gap_shift) / (
        MOREELS_LINEAR + math.sqrt(MOREELS_LINEAR**2 + 4 * MOREELS_QUADRATIC * inverse_gap_shift)
    )


def find_higher_peak(
    points: list[AbsorbancePoint], search_window: tuple[float, float]
) -> AbsorbancePoint:
    lower, upper = search_window
    candidates = [point for point in points if lower <= point.energy_ev <= upper]
    if len(candidates) < 3:
        raise ValueError("higher-energy peak search window needs at least three measured points")
    peak = max(candidates, key=lambda point: point.calculated_absorbance_au)
    if peak in (candidates[0], candidates[-1]):
        raise ValueError("peak search window does not bracket an interior maximum")
    return peak


def write_spectrum_data(
    points: list[AbsorbancePoint], solid_trace: list[AbsorbancePoint], path: Path
) -> None:
    columns = (
        *COLUMNS, "photon_energy_ev", "calculated_absorbance_au",
        "calculated_minus_exported_au", "plotted_in_solid_trace",
    )
    in_trace = set(solid_trace)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for point in points:
            calculated = point.calculated_absorbance_au
            writer.writerow({
                **asdict(point),
                "photon_energy_ev": point.energy_ev,
                "calculated_absorbance_au": calculated,
                "calculated_minus_exported_au": calculated - point.exported_absorbance_au,
                "plotted_in_solid_trace": point in in_trace,
            })


def plot_spectrum(
    points: list[AbsorbancePoint],
    peak: AbsorbancePoint,
    first_exciton_bounds: tuple[float, float],
    solid_trace: list[AbsorbancePoint],
    extension: list[AbsorbancePoint],
    path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(7.3, 4.6), layout="constrained")
    axis.axvspan(
        *first_exciton_bounds, color="#66a96f", alpha=0.45,
        label="First-exciton estimate",
    )
    axis.plot(
        [point.energy_ev for point in solid_trace],
        [point.calculated_absorbance_au for point in solid_trace],
        color="#176fa8", linewidth=1.75,
    )
    if extension:
        axis.plot(
            [point.energy_ev for point in extension],
            [point.calculated_absorbance_au for point in extension],
            color="#657681", linestyle=":", marker=".", markersize=4, linewidth=1.35,
            label="Additional export-edge samples",
        )
    axis.axvline(
        peak.energy_ev, color="#27333c", linestyle="--", linewidth=1.15,
        label=f"Higher-energy peak at {peak.energy_ev:.4f} eV",
    )

    lower = min(first_exciton_bounds[0], points[-1].energy_ev)
    upper = max(first_exciton_bounds[1], points[0].energy_ev)
    axis.set(
        xlim=(max(0.01, lower - 0.027), upper + 0.025),
        ylim=(
            min(0, min(point.calculated_absorbance_au for point in points)),
            max(0.25, 1.05 * max(point.calculated_absorbance_au for point in points)),
        ),
        xlabel="Photon energy (eV)",
        ylabel="Absorbance (a.u.)",
    )

    def reciprocal_scale(values):
        values = np.asarray(values, dtype=float)
        return np.divide(HC_EV_NM, values, out=np.full_like(values, np.inf), where=values != 0)

    wavelength_axis = axis.secondary_xaxis(
        "top", functions=(reciprocal_scale, reciprocal_scale)
    )
    wavelength_axis.set_xlabel("Wavelength (nm)")
    wavelength_axis.set_xticks([1800, 1700, 1600, 1500, 1400, 1300, 1200, 1100])
    axis.legend(loc="upper center", frameon=False, fontsize=8.2)
    figure.savefig(path, dpi=280, facecolor="white")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "absorbance")
    parser.add_argument(
        "--first-exciton-ev", nargs=2, type=float, metavar=("MIN", "MAX"),
        help="set the first-exciton energy interval used for size estimation",
    )
    parser.add_argument(
        "--higher-peak-window-ev", nargs=2, type=float, default=(0.83, 0.88),
        metavar=("MIN", "MAX"), help="search interval around the higher-energy absorption band",
    )
    args = parser.parse_args()

    try:
        if args.first_exciton_ev is None:
            first_exciton_bounds = tuple(
                HC_EV_NM / wavelength for wavelength in reversed(FIRST_EXCITON_RANGE_NM)
            )
            interval_source = "Estimated 1750–1800 nm interval at the long-wavelength edge"
        else:
            first_exciton_bounds = tuple(args.first_exciton_ev)
            interval_source = "user-supplied --first-exciton-ev interval"
        peak_window = tuple(args.higher_peak_window_ev)
        if not all(math.isfinite(value) for value in (*first_exciton_bounds, *peak_window)):
            raise ValueError("energy windows must be finite")
        if not first_exciton_bounds[0] < first_exciton_bounds[1] < peak_window[0] < peak_window[1]:
            raise ValueError("use increasing, non-overlapping first-exciton and higher-peak intervals")

        points = read_spectrum(args.input)
        peak = find_higher_peak(points, peak_window)
        diameters = sorted(moreels_diameter_nm(energy) for energy in first_exciton_bounds)
        first_exciton_wavelengths = [HC_EV_NM / energy for energy in reversed(first_exciton_bounds)]

        uses_bundled_export = args.input.resolve() == DEFAULT_INPUT.resolve()
        solid_trace = points
        if uses_bundled_export:
            solid_trace = [
                point for point in points if point.wavelength_nm <= SOLID_TRACE_LAST_WAVELENGTH_NM
            ] or points
        extension = points[len(solid_trace) - 1:] if len(solid_trace) < len(points) else []

        summary = {
            "input_csv": args.input.name,
            "sample_count": len(points),
            "wavelength_range_nm": [points[0].wavelength_nm, points[-1].wavelength_nm],
            "solid_trace_wavelength_range_nm": [
                solid_trace[0].wavelength_nm, solid_trace[-1].wavelength_nm
            ],
            "absorbance_calculation": "log10((reference_counts - dark_counts)/(sample_counts - dark_counts))",
            "max_absolute_difference_from_exported_absorbance_au": max(
                abs(point.calculated_absorbance_au - point.exported_absorbance_au) for point in points
            ),
            "higher_energy_peak_search_window_ev": peak_window,
            "higher_energy_peak": {
                "wavelength_nm": peak.wavelength_nm,
                "energy_ev": peak.energy_ev,
                "calculated_absorbance_au": peak.calculated_absorbance_au,
                "exported_absorbance_au": peak.exported_absorbance_au,
            },
            "first_exciton_sizing": {
                "status": "size estimated from a first-exciton energy interval",
                "interval_source": interval_source,
                "first_exciton_energy_range_ev": first_exciton_bounds,
                "first_exciton_wavelength_range_nm": first_exciton_wavelengths,
                "diameter_range_nm": diameters,
                "calibration": {
                    "reference": "Moreels et al., ACS Nano 3 (2009), p. 3024, Eq. (1)",
                    "doi": "10.1021/nn900863a",
                    "diameter_fit_range_nm": MOREELS_DIAMETER_RANGE_NM,
                    "diameter_interval_within_fit_range": all(
                        MOREELS_DIAMETER_RANGE_NM[0] <= value <= MOREELS_DIAMETER_RANGE_NM[1]
                        for value in diameters
                    ),
                },
            },
        }
        if uses_bundled_export:
            summary["acquisition"] = {
                "filename": "absorbance_1412003U1.TXT",
                "spectrometer": "1412003U1",
                "integration_ms": 17.00,
                "averaged_scans": 100,
                "smoothing_pixels": 0,
                "additional_edge_wavelengths_nm": [point.wavelength_nm for point in extension[1:]],
                "edge_interpretation": (
                    "Dark-corrected sample and reference counts fall near the long-wavelength "
                    "edge. The first-exciton maximum is unresolved in the usable trace."
                ),
            }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        plot_spectrum(
            points, peak, first_exciton_bounds, solid_trace, extension,
            args.output_dir / "ir-absorbance.png",
        )
        write_spectrum_data(
            points, solid_trace, args.output_dir / "absorbance_recalculated.csv"
        )
        (args.output_dir / "absorbance_summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"absorbance: {error}\n")

    print(
        f"Higher-energy peak: {peak.energy_ev:.6f} eV ({peak.wavelength_nm:.2f} nm). "
        f"Estimated diameter: {diameters[0]:.4f}–{diameters[1]:.4f} nm."
    )


if __name__ == "__main__":
    main()
