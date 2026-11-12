# Reproduced report figures

Regenerate these outputs with **python analysis/replicate.py --output-dir results/replication** from the repository root.

## Figure 10 · Infrared absorbance

The script calculates absorbance as log10((reference − dark) / (sample − dark)) and photon energy as hc/λ. The higher-energy peak at 1453.28 nm gives 0.853134 eV. The 1750–1800 nm first-exciton estimate comes from the original shaded interval and corresponds to 7.2098–7.5706 nm using Moreels Eq. (1). Two edge readings outside the original solid trace remain available in the processed table.

## Figure 14 · Current–voltage sweeps

Ordinary least-squares fits use the points visible in the original insets. The dark fit spans −0.05 to +0.15 V and gives 43.8383 MΩ. The illuminated fit spans −0.10 to +0.20 V and gives 2.2230 MΩ.

## Figure 15 · Spectral response

The photocurrent comes from the lock-in voltage across the 1 MΩ load. The Step-45 signal is divided by 10,560 V/W, then the aperture power is scaled by the detector-to-aperture area ratio. The device and calibration scans share 61 exact wavelengths. The 1260 nm peak gives 0.0796078 A/W and a Johnson-limited detectivity of 1.15823 × 10¹¹ Jones. The half-maximum crossing interpolates to 1339.73 nm, with the first sampled point below half maximum at 1340 nm.
