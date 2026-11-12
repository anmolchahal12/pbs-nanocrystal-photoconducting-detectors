"""Digitize and plot binned HAADF-STEM particle counts from Fig. 11."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SOURCE_IMAGE = ROOT / "figures" / "dark-field-tem.png"
IMAGE_SIZE = (1514, 790)
BAR_RGB = (31, 119, 180)
LEFT_TICK_PX = 1184
RIGHT_TICK_PX = 1496
MINIMUM_NM = 5.0
MAXIMUM_NM = 10.0
BIN_COUNT = 50


@dataclass(frozen=True)
class Panel:
    top_px: int
    bottom_px: int
    tick_rows_px: tuple[int, ...]
    tick_spacing_count: int

    @property
    def pixels_per_count(self) -> float:
        # Fit tick distances with the zero tick as a fixed origin.
        counts = [i * self.tick_spacing_count for i in range(1, len(self.tick_rows_px))]
        distances = [self.bottom_px - row for row in self.tick_rows_px[1:]]
        return sum(count * distance for count, distance in zip(counts, distances)) / sum(
            count**2 for count in counts
        )


# Pixel positions of the visible zero and major count ticks in the supplied raster.
FIELD_A = Panel(30, 354, (354, 293, 231, 169, 107, 46), 20)
FIELD_B = Panel(413, 737, (737, 699, 662, 624, 587, 550, 512, 475, 437), 20)


def digitize_panel(image: np.ndarray, panel: Panel) -> np.ndarray:
    if not all(
        (image[row, LEFT_TICK_PX - 4:LEFT_TICK_PX] == 0).all()
        for row in panel.tick_rows_px
    ):
        raise ValueError("Figure count ticks differ from the calibrated raster")

    centers_px = LEFT_TICK_PX + (
        (np.arange(BIN_COUNT) + 0.5) * (RIGHT_TICK_PX - LEFT_TICK_PX) / BIN_COUNT
    )
    counts = []
    for center_px in centers_px:
        pixels = image[panel.top_px:panel.bottom_px, math.floor(center_px)]
        filled = np.flatnonzero((pixels == BAR_RGB).all(axis=1))
        if not filled.size:
            counts.append(0)
            continue
        bar_top_px = panel.top_px + int(filled[0])
        height_count = (panel.bottom_px - bar_top_px) / panel.pixels_per_count
        count = round(height_count)
        if abs(height_count - count) > 0.49:
            raise ValueError("Bar height cannot be assigned a count reliably")
        counts.append(count)

    if not any(counts):
        raise ValueError("No histogram bars found in the calibrated panel")
    return np.asarray(counts)


def bin_statistics(centers_nm: np.ndarray, counts: np.ndarray) -> tuple[int, float, float]:
    total = int(counts.sum())
    mean = float(np.average(centers_nm, weights=counts))
    sd = math.sqrt(float(np.dot(counts, (centers_nm - mean) ** 2)) / (total - 1))
    return total, mean, sd


def save_bins(path: Path, edges_nm: np.ndarray, fields: tuple[np.ndarray, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("lower_nm", "upper_nm", "field_a_count", "field_b_count", "pooled_count"))
        for lower, upper, count_a, count_b in zip(edges_nm[:-1], edges_nm[1:], *fields):
            writer.writerow((f"{lower:.1f}", f"{upper:.1f}", count_a, count_b, count_a + count_b))


def save_plot(path: Path, edges_nm: np.ndarray, fields: tuple[np.ndarray, np.ndarray]) -> None:
    centers_nm = (edges_nm[:-1] + edges_nm[1:]) / 2
    labels = ("Field (a)", "Field (b)", "Pooled fields")
    colors = ("#207ba2", "#257d76", "#405f86")
    all_counts = (*fields, fields[0] + fields[1])
    figure, axes = plt.subplots(1, 3, figsize=(11.4, 3.7), sharex=True, layout="constrained")
    figure.suptitle("PbS nanocrystal diameter distribution from HAADF-STEM", fontweight="bold")

    for axis, label, color, counts in zip(axes, labels, colors, all_counts):
        total, mean, sd = bin_statistics(centers_nm, counts)
        axis.bar(
            edges_nm[:-1], counts, width=np.diff(edges_nm), align="edge",
            color=color, edgecolor="white", linewidth=0.35,
        )
        axis.axvline(mean, color="#243342", linewidth=1, linestyle="--")
        axis.set(
            title=f"{label}   |   n = {total:,}",
            xlabel="Particle diameter (nm)",
            ylabel="Particle count",
            xlim=(MINIMUM_NM, MAXIMUM_NM),
            ylim=(0, int(max(counts)) * 1.27),
        )
        axis.text(
            0.97, 0.96, f"{mean:.2f} ± {sd:.2f} nm",
            transform=axis.transAxes, ha="right", va="top", color="#243342",
            fontsize=9,
        )
        axis.grid(axis="y", color="#e1e7ed", linewidth=0.65)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=220, facecolor="white")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_IMAGE, help="Unscaled Fig. 11 PNG")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results",
        help="Directory for the binned CSV and histogram",
    )
    parser.add_argument(
        "--csv-out", type=Path, help="Override the binned CSV path",
    )
    parser.add_argument(
        "--plot-out", type=Path, help="Override the histogram path",
    )
    args = parser.parse_args()
    csv_out = args.csv_out or args.output_dir / "tem_histogram_bins.csv"
    plot_out = args.plot_out or args.output_dir / "tem-particle-distribution.png"

    try:
        with Image.open(args.source) as source:
            if source.size != IMAGE_SIZE:
                raise ValueError(f"Expected the unscaled {IMAGE_SIZE[0]} × {IMAGE_SIZE[1]} raster")
            image = np.asarray(source.convert("RGB"))
        fields = (digitize_panel(image, FIELD_A), digitize_panel(image, FIELD_B))
        edges_nm = np.linspace(MINIMUM_NM, MAXIMUM_NM, BIN_COUNT + 1)
        save_bins(csv_out, edges_nm, fields)
        save_plot(plot_out, edges_nm, fields)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    centers_nm = (edges_nm[:-1] + edges_nm[1:]) / 2
    for label, counts in zip(("Field (a)", "Field (b)", "Pooled"), (*fields, sum(fields))):
        total, mean, sd = bin_statistics(centers_nm, counts)
        print(f"{label}: {total:,} plotted particles, bin-midpoint mean ± sample SD {mean:.4f} ± {sd:.4f} nm")


if __name__ == "__main__":
    main()
