# PbS Nanocrystal Photoconducting Detectors

Reproduction of three figures from a materials science and engineering project on near-infrared lead sulfide (PbS) nanocrystal photoconductors. Absorbance and electron microscopy characterized the synthesized PbS colloid. The electrical and spectral scans used a photoconductor fabricated from a separate PbS batch.

## Replication results

| Quantity | Project report | Recalculated from Group 7 exports |
| --- | ---: | ---: |
| Higher-energy absorbance peak | 0.8531 eV | 0.853134 eV at 1453.28 nm |
| Diameter inferred from the estimated first exciton | 7.2097–7.5705 nm | 7.2098–7.5706 nm |
| Dark differential resistance | 43.84 MΩ | 43.8383 MΩ |
| Illuminated differential resistance | 2.22 MΩ | 2.2230 MΩ |
| Peak current responsivity | 0.0796 A/W at 1260 nm | 0.0796078 A/W at 1260 nm |
| Long-wavelength half-maximum cutoff | 1340 nm | 1339.73 nm by interpolation |
| Peak Johnson-limited specific detectivity | 1.1582 × 10¹¹ Jones | 1.15823 × 10¹¹ Jones |

The diameter estimate uses the 1750–1800 nm interval inferred from the original figure. The first-exciton maximum is unresolved at the usable long-wavelength edge of the scan. Specific detectivity uses a Johnson-noise model at 300 K and the fitted dark differential resistance.

| Report figure | Original plot | Reproduced plot |
| --- | --- | --- |
| Fig. 10 · Colloid absorbance | [Original](figures/ir-absorbance.png) | [From spectrometer counts](replicated/ir-absorbance.png) |
| Fig. 14 · Dark and illuminated I–V | [Original](figures/current-voltage.png) | [From recorded I–V sweeps](replicated/current-voltage.png) |
| Fig. 15 · Detector spectral response | [Original](figures/spectral-response.png) | [From device and calibration scans](replicated/spectral-response.png) |

![Reproduced photocurrent, power density, responsivity, and Johnson-limited detectivity](replicated/spectral-response.png)

## Reproduce the results

Use Python 3.10 or later. The [seven input CSVs](data/raw/) preserve the numerical readings and acquisition order of the Group 7 instrument exports.

~~~sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analysis/replicate.py --output-dir results/replication
~~~

The command rebuilds the three figures and writes intermediate CSVs and calculation summaries. It fits the I–V sweeps before using the dark resistance in the spectral detectivity calculation. [Saved results and calculation details](replicated/)

For an already calibrated detector spectrum, provide **wavelength_nm**, **photocurrent_a**, and **aperture_power_w**. For particle-level data, provide one ImageJ CSV per field with an **Area** column.

~~~sh
python analysis/detector.py --spectra path/to/spectrum.csv --output-dir results/detector
python analysis/microscopy.py --out-dir results/microscopy \
  --particles-csv path/to/field-a.csv \
  --particles-csv path/to/field-b.csv --area-unit nm2
~~~

Use **--area-unit px2 --nm-per-pixel SCALE** for pixel-area tables. Each command assumes a common pixel calibration across its supplied fields.

## Microscopy evidence

The [original HAADF-STEM figure](figures/dark-field-tem.png) reports a pooled diameter of 7.1378 ± 0.3204 nm (mean ± SD). The reported diffraction widths give a mean Scherrer coherent length of 5.3183 nm. The Group 7 archive and related project files provided the reported values and plots for these analyses. Particle-level ImageJ tables and SAED line profiles remain unavailable. The microscopy script reproduces the [mean-and-SD comparison](figures/tem-reported-summary.png) and [Scherrer length comparison](figures/scherrer-comparison.png) from the [reported tables](data/reported/).

## Sources

- Group 7 instrument exports and *Lead Sulphide Ligand Exchange Documentation*, p. 2, for the 10,560 V/W Step-45 calibration and the detector area.
- Project team report, *PbS Nanocrystal Photoconducting Detectors* (2025), pp. 6–10, Table 1 and Figs. 10–15, for the original plots, reported measurements and fit comparisons. Anmol Chahal prepared the repository from the project team's shared work.
- Moreels et al., *ACS Nano* **3**, 3023–3030 (2009), Eq. (1) and Fig. 2, for the empirical PbS diameter calibration over 3.9–13.3 nm. [Paper](https://doi.org/10.1021/nn900863a)
- Killilea et al., *Advanced Functional Materials* **29**, 1807964 (2019), for PbS ligand-shell photoconductor design and the relation between particle size and infrared response. [Paper](https://doi.org/10.1002/adfm.201807964)
- De Iacovo et al., *Scientific Reports* **6**, 37913 (2016), and *Applied Physics Letters* **111**, 211104 (2017), for near-infrared PbS photoconductors and experimental noise characterization. [Photoconductor measurements](https://doi.org/10.1038/srep37913) · [Noise measurements](https://doi.org/10.1063/1.5005805)
