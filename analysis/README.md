# Analysis workflows

- **replicate.py** runs the three analyses from the bundled raw CSVs. It passes the fitted dark I–V resistance to the detector calculation.
- **absorbance.py** reconstructs absorbance from dark-corrected counts and applies the Moreels sizing curve to the report's estimated first-exciton interval.
- **iv.py** fits the near-zero-bias portions of the dark and illuminated sweeps and reproduces Fig. 14.
- **detector.py** calibrates the measured lock-in scans on a common wavelength grid, calculates responsivity, and estimates Johnson-limited detectivity and the half-maximum cutoff. It also accepts an already calibrated spectral CSV.
- **microscopy.py** plots the reported TEM statistics, recalculates the Scherrer coherent lengths, and converts areas from supplied ImageJ tables into particle diameters.

See the [project README](../README.md) for the run commands and input columns.
