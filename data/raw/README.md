# Instrument data

These CSV files preserve the numerical readings and acquisition order of the instrument exports. Column names identify the measurements and units.

| CSV | Rows | Measurement |
| --- | ---: | --- |
| absorbance.csv | 256 | Wavelength, sample, dark and reference counts, and instrument absorbance |
| iv_dark.csv | 40 | Dark current–voltage sweep |
| iv_light.csv | 40 | Illuminated current–voltage sweep |
| iv_dark_positive.csv | 20 | Separate positive-bias dark sweep |
| iv_dark_negative.csv | 20 | Separate negative-bias dark sweep |
| photocurrent_scan.csv | 122 | Device lock-in amplitude and phase, 20 V supply and 1 MΩ load |
| pyrometer.csv | 101 | Step-45 calibration amplitude and phase, 1 mm aperture |

The spectrometer used 17 ms integration, 100 averaged scans, and zero pixel smoothing. The absorbance scan covers 1033.24–1762.53 nm. The device and calibration scans cover 1000–1605 nm and 1000–2000 nm, respectively. The Step-45 conversion uses 10,560 V/W from the instrument setup documentation.

The absorbance scan characterizes the synthesized PbS colloid. The electrical and spectral scans characterize the photoconductor fabricated from a separate batch. The microscopy inputs contain summary statistics and diffraction peak widths. [Microscopy inputs](../reported/)
