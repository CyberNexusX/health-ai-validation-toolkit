# Audit methods

## Reference and evaluation

The 2022 fitting and reference partitions are disjoint within each training clinic. Earlier cohort extraction produces one record per eligible synthetic patient. The two logistic regression pipelines each fit their own median imputation, missingness indicators, scaling, and coefficients on fitting rows alone. Both models are evaluated on identical patients in each evaluation window.

The reference cohort sets the comparison distribution for missingness and model scores. Outcome metrics use the evaluation cohort's complete simulated labels. The synthetic transportation barrier is sampled by age band, and missingness at Coastal depends on the underlying simulated barrier status. The random stream used to generate transportation is separate from the clinical fixture. The outcome generator has no transportation term.

## Calculation details

- Missingness change is the evaluation missing fraction minus the reference fraction.
- PSI sums the difference between current and reference bin proportions multiplied by the natural logarithm of their ratio. Both distributions use the fixed edges listed in the report. Add 0.5 to each bin count before normalizing to avoid taking the logarithm of zero.
- Calibration gap is mean predicted probability minus the observed outcome fraction. Calibration bins show average predicted probability and event fraction within each populated predicted-score range.
- Subgroup metrics use the same fitted models as the overall reports. An empty subgroup emits its zero count, and a one-class subgroup has no defined discrimination metrics.
- The example explanation multiplies each preprocessed feature by its fitted coefficient. The intercept plus contributions gives the log odds. The example is selected by auditing the first row with missing transportation status, falling back to the first row when none is missing.
