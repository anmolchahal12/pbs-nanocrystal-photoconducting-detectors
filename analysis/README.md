# Analysis workflows

- **detector.py** recomputes Johnson-limited sensitivity from reported values. With a spectral CSV, it scales the aperture power to the active area, divides photocurrent by power, and estimates the long-wavelength half-maximum crossing.
- **microscopy.py** plots the reported TEM statistics, recalculates the Scherrer coherent lengths, and converts areas from supplied ImageJ tables into particle diameters.

See the [project README](../README.md) for the run commands and input columns.
