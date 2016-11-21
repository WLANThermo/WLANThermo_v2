
## FANTAST
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](FANTAST_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>25</sub> | 164.01k
Resistance at 25°C | R<sub>25</sub> | 50.05k
Resistance at 85°C | R<sub>25</sub> | 5.44k
Beta 25°C to 85°C | B<sub>25/85</sub>| 3951K
Minimum measurable temperature | | 221.9°C
Minimum high-res temperature | | 90.6°C
Highest resolution || 2.20e-02°C/step at 20.1°C
Maximum high-res temperature | | -33.8°C
Maximum measurable temperature | | -62.5°C

### Probe curve data
![Probe fit chart](FANTAST_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 50.08k
Steinhart-Hart coefficient | a | 3.3558340e-03 ± 1.9359242e-07
Steinhart-Hart coefficient | b | 2.5698192e-04 ± 1.4451167e-07
Steinhart-Hart coefficient | c | 1.6391056e-06 ± 2.6808982e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
