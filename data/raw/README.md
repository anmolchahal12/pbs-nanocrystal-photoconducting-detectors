# Group 7 measurement exports

These CSV files preserve the numerical rows and acquisition order of the supplied Group 7 instrument exports. The conversion removes free-text instrument headers and uses explicit column names and units. The original archive contains the native exports and setup documentation.

| CSV | Original export | Rows | Use |
| --- | --- | ---: | --- |
| absorbance.csv | absorbance_1412003U1.TXT | 256 | Wavelength, sample, dark and reference counts, and exported absorbance |
| iv_dark.csv | dark iv | 40 | Complete dark I–V sweep for Fig. 14 |
| iv_light.csv | light iv | 40 | Complete illuminated I–V sweep for Fig. 14 |
| iv_dark_positive.csv | dark_plus_IV | 20 | Separate positive-bias dark sweep |
| iv_dark_negative.csv | dark_minus_IV | 20 | Separate negative-bias dark sweep |
| photocurrent_scan.csv | spectral_responsivity_20V_1MOhm | 122 | Device lock-in voltage and phase at 20 V supply, with a 1 MΩ series resistor |
| pyrometer.csv | pyrometer_1000-2000nm_1030nm_filter_1mm_iris.txt | 101 | Step-45 calibration lock-in voltage and phase, measured through a 1 mm diameter aperture |

The absorbance acquisition used 17 ms integration, 100 averaged scans, and no pixel smoothing. The instrument export covers 1033.24–1762.53 nm. The device scan ends at 1605 nm in the recorded rows, although its header lists a planned 2000 nm stop. The calibration scan covers 1000–2000 nm. The device and calibration scans were taken in January 2025 and November 2022, respectively.

The separately recorded positive and negative dark sweeps are included for reference. The fit in Fig. 14 uses the full dark and light sweep exports with the near-zero-bias windows shown in the report. The optical absorbance belongs to the synthesized PbS sample, and the electrical measurements belong to a device fabricated from a separate batch.

The Group 7 archive contains no original TEM particle table or diffraction line-profile export. The available TEM and SAED inputs are the [reported statistics and widths](../reported/).
