"""Recompute detector metrics and reproduce the measured spectral response."""

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOLTZMANN_J_PER_K = 1.380649e-23
LOAD_RESISTANCE_OHM = 1_000_000
STEP45_SENSITIVITY_V_PER_W = 10_560
REPORT_RESPONSE_LIMITS_NM = (1050, 1600)
PHOTOCURRENT_CSV = ROOT / "data/raw/photocurrent_scan.csv"
PYROMETER_CSV = ROOT / "data/raw/pyrometer.csv"
INSTRUMENT_COLUMNS = ("wavelength_nm", "lockin_voltage_v", "phase")
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


def load_summary(path: Path, positive_fields: tuple[str, ...]) -> dict:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    for key in positive_fields:
        value = values.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{path.name} field {key!r} must be a positive number.")
    return values


def load_reported_summary(path: Path) -> dict:
    return load_summary(path, SUMMARY_INPUTS)


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
            points.append(calibrate_point(wavelength, current, aperture_power, area_fraction,
                                          detectivity_factor))
    if len(points) < 2:
        raise ValueError("Spectrum CSV must contain at least two data rows.")
    if len({point.wavelength_nm for point in points}) != len(points):
        raise ValueError("Spectrum CSV contains duplicate wavelengths.")
    return sorted(points, key=lambda point: point.wavelength_nm)


def calibrate_point(wavelength: float, current: float, aperture_power: float,
                    area_fraction: float, detectivity_factor: float) -> SpectrumPoint:
    active_power = aperture_power * area_fraction
    if active_power <= 0 or not math.isfinite(active_power):
        raise ValueError(f"Invalid calibrated power at {wavelength:g} nm.")
    responsivity = current / active_power
    detectivity = responsivity * detectivity_factor
    if not math.isfinite(detectivity):
        raise ValueError(f"Non-finite detectivity at {wavelength:g} nm.")
    return SpectrumPoint(wavelength, current, aperture_power, active_power, responsivity, detectivity)


def read_instrument_scan(path: Path) -> dict[float, float]:
    """Read wavelength and lock-in amplitude. The archived phase is unused."""
    voltages = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not set(INSTRUMENT_COLUMNS).issubset(reader.fieldnames):
            raise ValueError(f"{path.name} requires columns " + ", ".join(INSTRUMENT_COLUMNS) + ".")
        for row in reader:
            try:
                wavelength, voltage, phase = (float(row[name]) for name in INSTRUMENT_COLUMNS)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path.name} line {reader.line_num} has an invalid number.") from error
            if (not all(math.isfinite(value) for value in (wavelength, voltage, phase))
                    or wavelength <= 0 or voltage < 0):
                raise ValueError(f"{path.name} line {reader.line_num} has an invalid measurement.")
            if wavelength in voltages:
                raise ValueError(f"{path.name} contains duplicate wavelength {wavelength:g} nm.")
            voltages[wavelength] = voltage
    if len(voltages) < 2:
        raise ValueError(f"{path.name} must contain at least two measurements.")
    return dict(sorted(voltages.items()))


def spectrum_metrics(points: list[SpectrumPoint]) -> dict:
    peak = max(points, key=lambda point: point.responsivity_a_per_w)
    if peak.responsivity_a_per_w <= 0:
        raise ValueError("The spectrum must contain a positive photocurrent amplitude.")

    cutoff = None
    cutoff_sample = None
    half_max = peak.responsivity_a_per_w / 2
    peak_index = points.index(peak)
    for left, right in zip(points[peak_index:], points[peak_index + 1 :]):
        if left.responsivity_a_per_w > half_max >= right.responsivity_a_per_w:
            fraction = (left.responsivity_a_per_w - half_max) / (
                left.responsivity_a_per_w - right.responsivity_a_per_w
            )
            cutoff = left.wavelength_nm + fraction * (right.wavelength_nm - left.wavelength_nm)
            cutoff_sample = right.wavelength_nm
            break

    return {
        "peak_wavelength_nm": peak.wavelength_nm,
        "peak_responsivity_a_per_w": peak.responsivity_a_per_w,
        "peak_johnson_detectivity_jones": peak.johnson_detectivity_jones,
        "half_max_cutoff_nm": cutoff,
        "first_sample_at_or_below_half_max_nm": cutoff_sample,
        "cutoff_definition": (
            "First falling half-maximum crossing at wavelengths above the peak, "
            "linearly interpolated. Null when outside the scanned range."
        ),
    }


def plot_raw_spectrum(points: list[SpectrumPoint], metrics: dict,
                      photocurrent: dict[float, float], aperture_power: dict[float, float],
                      aperture_area_mm2: float, detectivity_factor: float, directory: Path) -> None:
    """Rebuild the three panels of the report from the acquired and calibrated scans."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, (current_ax, power_ax, response_ax) = plt.subplots(
        1, 3, figsize=(15.2, 4.3), layout="constrained"
    )
    line_color = "#1b70aa"
    current_ax.plot(photocurrent.keys(), photocurrent.values(), color=line_color, lw=1.6)
    current_ax.set(title="(a) Photocurrent", ylabel="Photocurrent (A)")
    power_ax.plot(aperture_power.keys(),
                  [value / aperture_area_mm2 for value in aperture_power.values()],
                  color=line_color, lw=1.6)
    power_ax.set(title="(b) Incident power density", ylabel="Power density (W/mm²)")

    response_ax.plot([point.wavelength_nm for point in points],
                     [point.responsivity_a_per_w for point in points], color=line_color, lw=1.6)
    response_ax.set(title="(c) Responsivity and detectivity", ylabel="Responsivity (A/W)",
                    xlim=REPORT_RESPONSE_LIMITS_NM, ylim=(0, None))
    dstar_axis = response_ax.secondary_yaxis(
        "right", functions=(lambda value: value * detectivity_factor,
                            lambda value: value / detectivity_factor)
    )
    dstar_axis.set_ylabel("Johnson-limited D* (Jones)")
    dstar_axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)

    peak = metrics["peak_wavelength_nm"]
    response_ax.axvline(peak, color="#6a6f75", ls="--", lw=1.1)
    cutoff = metrics["half_max_cutoff_nm"]
    if cutoff is not None:
        half_max = metrics["peak_responsivity_a_per_w"] / 2
        response_ax.hlines(half_max, peak, cutoff, color="#008767", ls="--", lw=1.1)
        response_ax.vlines(cutoff, 0, half_max, color="#008767", ls="--", lw=1.1)

    current_ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    power_ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    for axis in (current_ax, power_ax, response_ax):
        axis.set_xlabel("Wavelength (nm)")
    figure.savefig(directory / "spectral-response.png", dpi=180, facecolor="white")
    plt.close(figure)


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
        figure.suptitle("PbS photoconductor spectral response", fontweight="bold")
        figure.savefig(directory / "detector_spectrum.png", dpi=300, facecolor="white")
        figure.savefig(directory / "detector_spectrum.svg", facecolor="white")
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "data/reported/detector.json")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--raw", action="store_true", help="Rebuild Figure 15 from the archived scans.")
    source.add_argument("--spectra", type=Path,
                        help="Measured CSV with " + ", ".join(SPECTRUM_COLUMNS))
    parser.add_argument("--iv-summary", type=Path, help="Use the resistances fitted from raw I–V scans.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/detector")
    args = parser.parse_args()

    try:
        reported = load_reported_summary(args.summary)
        recalculated = recompute_summary(reported)
        inputs = reported.copy()
        resistance_source = "Reported near-zero-bias I–V fits."
        if args.iv_summary:
            fields = ("dark_resistance_ohm", "illuminated_resistance_ohm")
            iv = load_summary(args.iv_summary, fields)
            inputs.update({field: iv[field] for field in fields})
            resistance_source = f"Raw I–V fits from {args.iv_summary.name}."
        calibration = recompute_summary(inputs)
        noise_current = calibration["johnson_current_noise_a_per_sqrt_hz"]
        detectivity_factor = math.sqrt(inputs["active_area_mm2"] / 100) / noise_current
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
        points = None
        if args.spectra:
            points = load_spectrum(
                args.spectra,
                calibration["active_area_power_fraction"],
                detectivity_factor,
            )
        if args.raw:
            photocurrent = {
                wavelength: voltage / LOAD_RESISTANCE_OHM
                for wavelength, voltage in read_instrument_scan(PHOTOCURRENT_CSV).items()
            }
            aperture_power = {
                wavelength: voltage / STEP45_SENSITIVITY_V_PER_W
                for wavelength, voltage in read_instrument_scan(PYROMETER_CSV).items()
            }
            common_wavelengths = sorted(photocurrent.keys() & aperture_power.keys())
            if len(common_wavelengths) < 2:
                raise ValueError("The detector and pyrometer scans must share at least two wavelengths.")
            points = [
                calibrate_point(wavelength, photocurrent[wavelength], aperture_power[wavelength],
                                calibration["active_area_power_fraction"], detectivity_factor)
                for wavelength in common_wavelengths
            ]
            peak_current_wavelength = max(photocurrent, key=photocurrent.__getitem__)
            peak_power_wavelength = max(aperture_power, key=aperture_power.__getitem__)
            summary["raw_scan_calibration"] = {
                "photocurrent_scan": str(PHOTOCURRENT_CSV.relative_to(ROOT)),
                "pyrometer_scan": str(PYROMETER_CSV.relative_to(ROOT)),
                "load_resistance_ohm": LOAD_RESISTANCE_OHM,
                "active_area_mm2": inputs["active_area_mm2"],
                "calibration_aperture_diameter_mm": inputs["calibration_aperture_diameter_mm"],
                "step45_sensitivity_v_per_w": STEP45_SENSITIVITY_V_PER_W,
                "sensitivity_source": "Lead Sulphide Ligand Exchange Documentation, PDF p. 2.",
                "calibration_aperture_area_mm2": calibration["calibration_aperture_area_mm2"],
                "active_area_power_fraction": calibration["active_area_power_fraction"],
                "photocurrent_sample_count": len(photocurrent),
                "photocurrent_wavelength_range_nm": [min(photocurrent), max(photocurrent)],
                "pyrometer_sample_count": len(aperture_power),
                "pyrometer_wavelength_range_nm": [min(aperture_power), max(aperture_power)],
                "paired_sample_count": len(points),
                "wavelength_alignment": "Exact matching between the 5 nm and 10 nm scan grids.",
                "paired_wavelength_range_nm": [points[0].wavelength_nm, points[-1].wavelength_nm],
                "response_plot_window_nm": list(REPORT_RESPONSE_LIMITS_NM),
                "peak_photocurrent_a": photocurrent[peak_current_wavelength],
                "peak_photocurrent_wavelength_nm": peak_current_wavelength,
                "peak_aperture_power_w": aperture_power[peak_power_wavelength],
                "peak_incident_power_density_w_per_mm2": (
                    aperture_power[peak_power_wavelength] / calibration["calibration_aperture_area_mm2"]
                ),
                "peak_power_wavelength_nm": peak_power_wavelength,
            }
        if points is not None:
            metrics = spectrum_metrics(points)
            metrics["dark_resistance_ohm"] = inputs["dark_resistance_ohm"]
            metrics["illuminated_resistance_ohm"] = inputs["illuminated_resistance_ohm"]
            metrics["resistance_source"] = resistance_source
            metrics["temperature_k"] = inputs["temperature_k"]
            metrics["johnson_current_noise_a_per_sqrt_hz"] = noise_current
            metrics["peak_johnson_nep_w_per_sqrt_hz"] = noise_current / metrics["peak_responsivity_a_per_w"]
            summary["computed_from_input_spectrum"] = metrics

        args.output_dir.mkdir(parents=True, exist_ok=True)
        if points is not None:
            if args.raw:
                plot_raw_spectrum(points, metrics, photocurrent, aperture_power,
                                  calibration["calibration_aperture_area_mm2"],
                                  detectivity_factor, args.output_dir)
            else:
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
