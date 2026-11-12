"""Recompute reported detector metrics and analyze an optional measured spectrum."""

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOLTZMANN_J_PER_K = 1.380649e-23
SPECTRUM_COLUMNS = ("wavelength_nm", "photocurrent_a", "aperture_power_w")
SUMMARY_INPUTS = (
    "dark_resistance_ohm",
    "illuminated_resistance_ohm",
    "active_area_mm2",
    "calibration_aperture_diameter_mm",
    "temperature_k",
    "peak_responsivity_a_per_w",
)


@dataclass(frozen=True)
class SpectrumPoint:
    wavelength_nm: float
    photocurrent_a: float
    aperture_power_w: float
    active_area_power_w: float
    responsivity_a_per_w: float
    johnson_detectivity_jones: float


def load_reported_summary(path: Path) -> dict:
    reported = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(reported, dict):
        raise ValueError("The summary JSON must contain a JSON object.")
    for key in SUMMARY_INPUTS:
        value = reported.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"Summary field {key!r} must be a positive number.")
    return reported


def recompute_summary(reported: dict) -> dict:
    """Use the equilibrium noise of the reported near-zero-bias dark resistance."""
    aperture_area_mm2 = math.pi * (reported["calibration_aperture_diameter_mm"] / 2) ** 2
    area_fraction = reported["active_area_mm2"] / aperture_area_mm2
    area_cm2 = reported["active_area_mm2"] / 100
    dark_resistance = reported["dark_resistance_ohm"]
    noise_current = math.sqrt(
        4 * BOLTZMANN_J_PER_K * reported["temperature_k"] / dark_resistance
    )
    peak_responsivity = reported["peak_responsivity_a_per_w"]
    peak_nep = noise_current / peak_responsivity
    return {
        "calibration_aperture_area_mm2": aperture_area_mm2,
        "active_area_power_fraction": area_fraction,
        "dark_to_illuminated_resistance_ratio": (
            dark_resistance / reported["illuminated_resistance_ohm"]
        ),
        "resistance_area_product_ohm_cm2": dark_resistance * area_cm2,
        "johnson_current_noise_a_per_sqrt_hz": noise_current,
        "peak_johnson_nep_w_per_sqrt_hz": peak_nep,
        "peak_johnson_detectivity_jones": math.sqrt(area_cm2) / peak_nep,
    }


def load_spectrum(path: Path, area_fraction: float, detectivity_factor: float) -> list[SpectrumPoint]:
    points = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not set(SPECTRUM_COLUMNS).issubset(reader.fieldnames):
            raise ValueError("Spectrum CSV requires columns " + ", ".join(SPECTRUM_COLUMNS) + ".")
        for row in reader:
            try:
                wavelength, current, aperture_power = (float(row[name]) for name in SPECTRUM_COLUMNS)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Spectrum CSV line {reader.line_num} has an invalid number.") from error
            if not all(math.isfinite(value) for value in (wavelength, current, aperture_power)):
                raise ValueError(f"Spectrum CSV line {reader.line_num} has a non-finite value.")
            if wavelength <= 0 or current < 0 or aperture_power <= 0:
                raise ValueError(
                    f"Spectrum CSV line {reader.line_num} requires positive wavelength and "
                    "aperture power and a nonnegative photocurrent amplitude."
                )
            active_power = aperture_power * area_fraction
            if active_power <= 0 or not math.isfinite(active_power):
                raise ValueError(f"Spectrum CSV line {reader.line_num} has invalid calibrated power.")
            responsivity = current / active_power
            detectivity = responsivity * detectivity_factor
            if not math.isfinite(detectivity):
                raise ValueError(f"Spectrum CSV line {reader.line_num} produces non-finite detectivity.")
            points.append(
                SpectrumPoint(
                    wavelength, current, aperture_power, active_power, responsivity, detectivity,
                )
            )
    if len(points) < 2:
        raise ValueError("Spectrum CSV must contain at least two data rows.")
    if len({point.wavelength_nm for point in points}) != len(points):
        raise ValueError("Spectrum CSV contains duplicate wavelengths.")
    return sorted(points, key=lambda point: point.wavelength_nm)


def spectrum_metrics(points: list[SpectrumPoint]) -> dict:
    peak = max(points, key=lambda point: point.responsivity_a_per_w)
    if peak.responsivity_a_per_w <= 0:
        raise ValueError("The spectrum must contain a positive photocurrent amplitude.")

    cutoff = None
    half_max = peak.responsivity_a_per_w / 2
    peak_index = points.index(peak)
    for left, right in zip(points[peak_index:], points[peak_index + 1 :]):
        if left.responsivity_a_per_w > half_max >= right.responsivity_a_per_w:
            fraction = (left.responsivity_a_per_w - half_max) / (
                left.responsivity_a_per_w - right.responsivity_a_per_w
            )
            cutoff = left.wavelength_nm + fraction * (right.wavelength_nm - left.wavelength_nm)
            break

    return {
        "peak_wavelength_nm": peak.wavelength_nm,
        "peak_responsivity_a_per_w": peak.responsivity_a_per_w,
        "peak_johnson_detectivity_jones": peak.johnson_detectivity_jones,
        "half_max_cutoff_nm": cutoff,
        "cutoff_definition": (
            "First falling half-maximum crossing at wavelengths above the peak, "
            "linearly interpolated. Null when outside the scanned range."
        ),
    }


def plot_spectrum(points: list[SpectrumPoint], metrics: dict, directory: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    wavelengths = [point.wavelength_nm for point in points]
    series = (
        ("Photocurrent (nA)", [point.photocurrent_a * 1e9 for point in points], "#0072b2"),
        ("Power on active area (µW)", [point.active_area_power_w * 1e6 for point in points], "#008767"),
        ("Responsivity (A/W)", [point.responsivity_a_per_w for point in points], "#0072b2"),
        ("Johnson-limited D* (Jones)", [point.johnson_detectivity_jones for point in points], "#a34726"),
    )
    style = {
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": "#20303a",
        "axes.edgecolor": "#576974",
        "grid.color": "#dae2e8",
        "xtick.color": "#20303a",
        "ytick.color": "#20303a",
        "svg.fonttype": "none",
    }
    with plt.rc_context(style):
        figure, axes = plt.subplots(2, 2, figsize=(9, 5.7), sharex=True, layout="constrained")
        for index, (axis, (label, values, color)) in enumerate(zip(axes.flat, series)):
            axis.plot(wavelengths, values, color=color, linewidth=1.65)
            axis.set_ylabel(label)
            axis.grid(axis="y", linewidth=0.7)
            axis.set_axisbelow(True)
            axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
            if index >= 2:
                axis.set_xlabel("Wavelength (nm)")
                axis.axvline(
                    metrics["peak_wavelength_nm"], color="#63727e", linestyle=":", label="Peak"
                )
                cutoff = metrics["half_max_cutoff_nm"]
                if cutoff is not None:
                    axis.axvline(cutoff, color="#008767", linestyle="--", label="50% cutoff")
        axes[1, 0].legend(frameon=False, fontsize=8)
        figure.suptitle("PbS photoconductor spectral response", fontweight="semibold")
        figure.savefig(directory / "detector_spectrum.png", dpi=300, facecolor="white")
        figure.savefig(directory / "detector_spectrum.svg", facecolor="white")
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "data/reported/detector.json")
    parser.add_argument("--spectra", type=Path, help="Measured CSV with " + ", ".join(SPECTRUM_COLUMNS))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/detector")
    args = parser.parse_args()

    try:
        reported = load_reported_summary(args.summary)
        recalculated = recompute_summary(reported)
        summary = {
            "reported": reported,
            "recomputed_from_reported": recalculated,
            "power_calibration": (
                "The average irradiance over the calibration aperture is assumed to "
                "represent the irradiance at the detector."
            ),
            "noise_model": (
                "Johnson noise only, using the near-zero-bias dark resistance "
                "and stated temperature. Operating noise was not measured."
            ),
        }
        if args.spectra:
            points = load_spectrum(
                args.spectra,
                recalculated["active_area_power_fraction"],
                recalculated["peak_johnson_detectivity_jones"] / reported["peak_responsivity_a_per_w"],
            )
            metrics = spectrum_metrics(points)
            summary["computed_from_input_spectrum"] = metrics

        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.spectra:
            plot_spectrum(points, metrics, args.output_dir)
            with (args.output_dir / "detector_spectrum.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=SpectrumPoint.__dataclass_fields__)
                writer.writeheader()
                writer.writerows(asdict(point) for point in points)
        (args.output_dir / "detector_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))

    print(f"Detector outputs: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
