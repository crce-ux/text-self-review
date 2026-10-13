# Pre-treatment resting-state EEG alpha power and ECT response in treatment-resistant depression: a retrospective cohort study

## Abstract

**Background.** Electroconvulsive therapy (ECT) is effective in treatment-resistant depression (TRD), but response is heterogeneous. We examined whether pre-treatment resting-state EEG alpha power predicts ECT response.

**Methods.** We retrospectively reviewed 248 patients with TRD who received an acute ECT course between 2019 and 2024. Pre-treatment resting-state EEG was recorded within 72 hours before the first session. The primary outcome was response (≥50% reduction in MADRS) after the acute course. Discrimination was assessed by the concordance index. Statistical significance was set at P < 0.05.

**Results.** 231 patients entered the per-protocol analysis after 17 exclusions (9 withdrew consent, 5 had unusable EEG, 3 received fewer than 6 sessions). Response occurred in 148 of 231 (64.1%). Alpha power was associated with response (OR 1.42 per SD, 95% CI 1.11–1.82, P = 0.005). The concordance index was 0.63 (95% CI 0.55–0.71).

**Conclusions.** Pre-treatment alpha power is modestly associated with ECT response. Discrimination is insufficient for individual-level prediction.

## Methods

### Participants

Consecutive patients meeting DSM-5 criteria for major depressive disorder with a documented failure of at least two adequate antidepressant trials were eligible. 248 patients were enrolled.

### EEG acquisition

Resting-state EEG was recorded for 10 minutes with eyes closed (19 channels, 256 Hz). After artefact rejection, alpha power (8–12 Hz) was averaged across posterior channels.

### Missing data

Baseline covariates with missing values (n = 12 for BMI, n = 7 for illness duration) were handled by **multiple imputation** (5 imputations, chained equations). Time-varying variables with missing visits were carried forward using **last observation carried forward (LOCF)**.

### Statistical analysis

Logistic regression with alpha power as the primary predictor, adjusted for age, sex, and baseline MADRS. Discrimination was evaluated by the concordance index. **Calibration was assessed by the calibration slope (observed 1.08) and a calibration plot with loess smoothing (Figure 2).**

### Sensitivity analyses

Because the per-protocol analysis excluded 17 patients, we repeated the primary model on the full analysis set (n = 248) using multiple imputation for the outcome. Results were materially unchanged.

## Results

Response occurred in 148/231 (64.1%). The adjusted odds ratio for alpha power was 1.42 per SD (95% CI 1.11–1.82, P = 0.005). The concordance index was 0.63 (95% CI 0.55–0.71). Calibration was adequate (slope 1.08, 95% CI 0.86–1.30).

## Limitations

This is a single-centre retrospective study. EEG was recorded at a single time point. The concordance index of 0.63 limits the usefulness of this model for individual-level clinical decision-making.

## Figures

- Figure 1. Participant flow diagram.
- Figure 2. Calibration plot with loess smoothing.

## References

1. Smith A, et al. Alpha power and antidepressant response. *J Affect Disord*. 2021;280:112-119.
2. Chen L, et al. EEG biomarkers in electroconvulsive therapy. *Biol Psychiatry*. 2022;91(4):355-364.
3. Okafor N, et al. Calibration assessment in clinical prediction models. *Stat Med*. 2020;39(15):2101-2115.
