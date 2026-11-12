# Analysis

Run the optical and electrical analysis from the repository root.

```sh
python analysis/replicate.py --output-dir results
```

- **absorbance.py** calculates absorbance from dark-corrected spectrometer counts and estimates nanocrystal diameter using the Moreels sizing relation.
- **iv.py** fits the near-zero-bias sections of the dark and illuminated sweeps.
- **detector.py** calibrates photocurrent and optical power on a common wavelength grid and calculates responsivity, Johnson-noise-limited detectivity, and the half-maximum cutoff.
- **microscopy.py** analyzes ImageJ area exports and uses fitted diffraction peak widths to estimate coherent length.
- **particle_histogram.py** digitizes the two HAADF-STEM histogram panels and plots the field and pooled particle-size distributions.

The pipeline passes the fitted dark resistance to the detectivity calculation.

Generate the microscopy plots and bin counts with the following commands.

```sh
python analysis/microscopy.py --out-dir results
python analysis/particle_histogram.py --output-dir results
```
