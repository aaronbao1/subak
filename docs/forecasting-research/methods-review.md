# Forecasting method comparison and candidate selection

**Proposed design:** compare methods along independent dimensions: forecast target, learning unit, parameter sharing, horizon strategy, contextual inputs and uncertainty construction. A family name does not answer all six. No public benchmark establishes the best enterprise-spend architecture.

**Established evidence** is documented with primary citations in the linked specialist tracks. **Inference:** current financial coverage and effective sample support are likely to constrain useful complexity. **Unvalidated hypotheses:** global boosted trees, partial pooling, richer context or a pretrained model can improve the target; any may fail on short, shifting, sparse financial histories.

## Comprehensive scoped taxonomy

| Family and primary review | What to compare | Data/assumption requirements | Distinct rejection risk |
|---|---|---|---|
| [Classical and structural](tracks/06-classical.md) | Calendar run rates; seasonal naive; ETS; ARIMA/SARIMA; regression with ARIMA errors; dynamic/Bayesian structural models; Fourier/TBATS; additive Prophet; small VAR/VARX; GP | Sufficient complete cycles, identifiable parameters; known versus estimated future regressors | Trend extrapolation, transformed median mistaken for mean, Gaussian negative support, future-regressor leakage |
| [Intermittent and compound](tracks/07-intermittent.md) | Croston/SBA/TSB; ADIDA/IMAPA; hurdle/zero-inflated count; negative binomial; compound/Tweedie; frequency-severity models | Verified zero/exposure mask, sufficient occurrences and positive outcomes; dependence diagnosis | Outages interpreted as deactivation, unsupported native intervals, burst deletion, multiplication of dependent factor means |
| [Pooling and multilevel](tracks/08-pooling.md) | Local vs global regression; partial pooling; crossed effects; cohort/multitask models; aggregate summary features | Comparable target semantics and historical entity metadata; cohort support | Negative transfer, person/project confounding, identity memorization, scarce long-run regimes despite many rows |
| [Reconciliation](tracks/09-reconciliation.md) | Bottom-up/top-down/middle-out; OLS/WLS/shrinkage MinT; nonnegative/general constraints; probabilistic and cross-temporal methods | Exhaustive accounting partition or justified constraints; aligned residuals at target horizon | Coherence mistaken for accuracy/calibration, unstable covariance, calendars that do not nest, invalid sampler combinations |
| [Tabular ML](tracks/10-tabular.md) | Elastic net/GAM/forests; LightGBM/XGBoost/CatBoost; mean/quantile/distributional objectives; recursive versus direct cumulative | Strictly as-of lag/rolling features; sufficient origins; entity/category normalization | Leakage through rolling features/labels, subgroup loss, crossing quantiles, horizon incoherence, imputed future drivers |
| [Task-trained neural](tracks/11-neural.md) | DeepAR/TCN; N-BEATS/N-HiTS; TFT; DLinear; PatchTST/iTransformer; TiDE/TSMixer variants | Adequate comparable training series and independent evaluation; pinned implementation covariate flags | Model name implies nonexistent adapter capability, expensive overfit, quantile-head output mistaken for expected cost |
| [Foundation models](tracks/12-foundation.md) | Current Chronos, TimesFM, Moirai, Toto, TimeGPT, Lag-Llama, TiRex, t0 and Timestral candidates | Valid checkpoint/service license and supported feature/output interface; domain and contamination checks | Unrestricted code but restricted weights, preview service, unmeasured inference costs, benchmark transfer failure |
| [Text and judgment](tracks/13-context.md) | Structured events; embeddings; direct LLM; numeric revisions/ensembles; human manager forecasts; explanation-only | Available-at corpus, reproducible extraction and evidence; blinded human labels | Outcome-selected events, invented effects, irrelevant context sensitivity, persuasive uncalibrated revisions |
| [Change/adaptation](tracks/14-change.md) | Recent/long/discounted experts; interventions; BOCPD/CUSUM/ADWIN; regime switching; registered adaptive ensemble | Stable observation basis; delivered labels; calibrated false-alarm/delay behavior | Connector outage called behavioral change, destructive resets, fleet-wide multiple alarms, budget censoring |
| [Probabilistic methods](tracks/15-uncertainty.md) | Parametric and distributional models; residual/block bootstrap; joint simulation/copulas; conformal/ACI/EnbPI | Exact target and mature calibration outcomes; justified time/entity dependence | Marginal guarantee sold as conditional assurance; too-wide intervals; delayed feedback ignored |
| [Session processes](tracks/16-sessions.md) | Daily activity features; session arrivals/severity; marked processes; survival/prefix continuation | Stable session/run/attempt identity and horizon-clipped consumption | Finished-only selection, full eventual bill booked at start, shared prefix double-counting, wall time used as tokens |
| [Selection and decision methods](tracks/17-evaluation.md) | Fixed candidates; ensembles; adaptive configuration procedures; capability-based promotion | Search budget and untouched final origins; costs/failures measured | Repeated final-holdout tuning, cherry-picked eligible origins, claimed gains from synthetic fixtures |

This is a broad decision-oriented review, not a claim that every published forecasting algorithm has been exhaustively screened. Graph neural and causal structural variants, universal AutoML search, exotic extreme-value extrapolation and full agent-based simulation should enter only when a specific identifiable mechanism and data support justify a comparison. Complexity alone is not new evidence.

## Formulation choices

**Direct money** predicts the monetary target with the fewest intermediate modeled quantities. It can adapt implicitly to historical mix, but cannot explain a new price regime purely from old spend. **Activity and severity** separates active occurrence/count and conditional cost, useful for sparse demand and workforce scenarios. **Usage and pricing** forecasts billable categories then applies verified contract logic, useful for known price changes and model-mix scenarios. All three must be scored against the same eventual target or clearly identified as different exercises.

Mathematically, dependence and nonlinearity matter: `E[A*C]` is generally not `E[A]*E[C]`, and `E[g(U)]` is generally not `g(E[U])`. A decomposition needs joint conditional modeling, defensible assumptions or a direct-total comparator. Meter counts and net adjustments may have different support; credits/refunds are not negative tasks.

## Initial executable comparison set

The selected architecture should implement a modest, useful candidate registry before optional heavyweight adapters:

1. Last complete observation, trailing complete-calendar-window mean, weekday mean, seasonal naive and simple exponential smoothing. Explicitly state window and eligibility. A seasonal-naive week repeats the last matching weekday over exact requested dates.
2. Local-level/damped trend and regularized calendar/lag regression. Add SARIMA/dynamic regression when enough history supports it; keep small parameter/search budgets.
3. Pooled regularized models on teams; then aggregate individual summaries and pooled individuals on an identical covered population. Compare learning level separately from aggregation level.
4. One strong global tabular implementation with regularized feature set and direct cumulative targets as well as a daily-path comparator. Admit occurrence/positive-severity objectives when verified intermittency warrants them.
5. Reconciliation and calibrated cumulative outputs as distinct modules; direct totals remain challengers. Optional neural/foundation/session/context models are admitted only after input and evaluation gates.

This ordering manages engineering and evidence cost. It is not a claim the first method is most accurate or that the fifth must win. A zero-shot foundation adapter can be evaluated early if legal, inexpensive and technically straightforward, but it receives the same information and evaluation rules. Document unavailable methods rather than returning mock output under their names.

## Horizon and statistic choices

The experimental finance targets are cumulative 7/14/30 calendar days and remaining calendar month. Compare daily and weekly modeled grids while scoring identical target intervals; evaluate direct horizon totals as well. Each horizon may require different forecast-error covariance and calibration support. Parameter refit frequency is distinct from state updates, request frequency and UI refresh.

Expected spending requires an original-scale predictive mean. Medians target typical outcomes and upper quantiles target risk decisions. A logged forecast transformed back is not automatically a mean. A finite quantile grid does not identify a tail mean or a joint distribution. Evaluate the actual statistic, not whichever number an adapter calls “point forecast.”

## Configuration and deployment gates

Pin package/checkpoint/service and feature flags, not just model family. Official releases sometimes add covariate support absent from the paper, while generic constructor arguments can expose unsupported inputs. The [neural audit](tracks/11-neural.md), [foundation audit](tracks/12-foundation.md) and [reconciliation audit](tracks/09-reconciliation.md) identify specific examples. Code, weights, datasets and managed-service terms have separate licenses. Re-check living documentation before deployment.

Record cold/warm latency, training time, memory, hardware, series count, context/horizon, API/token cost, source/extraction cost, invalid/fallback rate and maintenance burden. Author-reported throughput is not an enterprise cost estimate. A managed service can be commercially available yet preview-only or batch-only; availability is an explicit eligibility fact.

The winner is the lowest-burden configuration that passes registered target, data, point-score, bias, cohort, operations and relevant probabilistic/decision gates. Inconclusive differences retain the simpler eligible incumbent. No universal numeric promotion margin is asserted without finance and dataset evidence.
