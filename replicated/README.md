# Optical and electrical results

Generate the plots and tables with `python analysis/replicate.py --output-dir results` from the repository root.

## Infrared absorbance

Dark-corrected reference and sample counts give the absorbance, and photon energy follows from the measured wavelength. The higher-energy absorption peak is 0.853134 eV at 1453.28 nm. Applying the Moreels sizing relation to the estimated 1750–1800 nm first-exciton interval gives a diameter of 7.2098–7.5706 nm. The first-exciton maximum is unresolved in the usable scan.

[Absorbance plot](ir-absorbance.png) · [Data table](absorbance_recalculated.csv) · [Summary](absorbance_summary.json)

## Current–voltage measurements

Near-zero-bias least-squares fits give 43.8383 MΩ in the dark and 2.2230 MΩ under illumination. The fits span −0.05 to +0.15 V and −0.10 to +0.20 V, respectively.

[Current–voltage plot](current-voltage.png) · [Data table](iv_recalculated.csv) · [Summary](iv_summary.json)

## Spectral response

The current follows from the voltage across the 1 MΩ load. The optical calibration uses the Step-45 sensitivity of 10,560 V/W and the detector-to-aperture area ratio. The responsivity peaks at 0.0796078 A/W at 1260 nm. The Johnson-noise model gives 1.15823 × 10¹¹ Jones at the peak. The interpolated half-maximum cutoff is 1339.73 nm.

[Spectral-response plot](spectral-response.png) · [Data table](detector_spectrum.csv) · [Summary](detector_summary.json)
