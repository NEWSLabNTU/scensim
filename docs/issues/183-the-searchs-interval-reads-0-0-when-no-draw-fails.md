# 183: the search's interval reads [0, 0] when no draw fails

**Status:** fixed in code and tests (plan approved by 133, 2026-11-25).
**Severity:** medium. A search that sees no failure reports an interval of [0, 0] under the name
of a 95 % interval, which reads as "the rate is 0" when the run says only that it is small.
**Found:** 2026-11-25, scensim 241, 092 K13 step v: the platoon search on Town05 ran 20
generations and a fresh stage of 1000 draws with no failure, and the tool printed p 0, [0, 0].

## What happens

`scensim_sampler.search.plain_estimate` reports the plain likelihood-ratio estimate with a
normal 95 % interval, p plus or minus 1.96 SE, labelled "plain likelihood ratio, normal 95 %".
SE is estimated from the weighted failure indicators, so its spread comes from the failures
themselves. With no failure in the fresh stage every term `w * f` is 0: p is 0, SE is 0, and the
relative-error term (p times the normaliser's relative error) is 0 as well. The interval prints
as [0, 0].

That is not an answer. Zero failures in n draws bounds the rate from above; it does not put it
at 0. A search with only a few failures is hit in a weaker form: the normal interval is poor at
small counts, and its lower end is clipped at 0.

## Scope

Every search whose fresh stage has no failure, whatever the case; the normal interval is
unreliable at a few failures. The point estimate p and Kish's n_eff are not affected.

## Proposed fix

1. **At 0 failures, an exact upper bound through the mixture's weight cap.** The fresh stage
   draws from the defensive mixture q = beta f + (1 - beta) g (f the base, g the fitted
   cross-entropy density), so f / q is at most 1 / beta everywhere. With constraints the weight
   is (f / q) (Z_q / Z_b), the second factor the record's `search.normaliser` (search.py's
   module docstring), so every weight is at most normaliser / beta. With F the failure set,
   p = E_q[w 1_F] <= (normaliser / beta) q(F), and q(F) is a plain binomial proportion of the
   fresh stage's n draws. The bound holds without any assumption about where F lies. It is
   loose, and the record says so: it charges every failure the largest weight the mixture can
   give, which is 10 at beta 0.1.

   **The normaliser's error (Bonferroni, fixed now).** The bound is a one-sided 95 % upper
   confidence bound, total miss probability 0.05, split three ways:
   - q(F): the Clopper-Pearson upper bound at 0.025, 1 - 0.025^(1/n) at 0 of n;
   - Z_q (the mixture's acceptance, z_proposal of m_q draws): its Clopper-Pearson upper bound
     at 0.0125;
   - Z_b (the base's acceptance, z_base of m_b draws): its Clopper-Pearson lower bound at
     0.0125.

   The bound is then U = (Z_q upper / Z_b lower) (1 - 0.025^(1/n)) / beta, and the interval is
   [0, U]. With no constraints both acceptances are m of m; the factor is still applied (at
   m 100000 each end moves by 4.4e-5), so one rule covers every search. For n 1000, beta 0.1
   and no constraints, U is 3.68e-2. Its method name says what it is: "0 failures: exact
   one-sided 95 % bound through the mixture's weight cap (normaliser by Bonferroni)".
2. **At a few failures, a Wilson score interval on the effective sample size**, the weighted p
   with Kish's n_eff in place of n. It is an approximation and the record labels it so
   ("approximate: Wilson score on n_eff"); only the zero-failure bound is exact. The normal
   interval stays in the record for comparison, not as the headline. Where the score interval
   gives way to the normal one, if anywhere, the plan fixes.
3. **Name the method that was used.** `interval_method` names the method actually applied,
   with "exact" or "approximate" in it, and `search report` prints the failure count next to
   the interval, so a reader sees 0 of 1000 before any number.

Tests: 0 failures gives U against the closed form (n 1000, beta 0.1, with and without
constraints); a few failures give the score interval, labelled approximate; many failures give
an interval close to the normal one; the record and the report name the method.

## The plan (approved by 133, 2026-11-25, before any code)

Today `search.plain_estimate(log_w, normaliser, failed, rel_err)` returns p, se, a normal
interval, n_eff and the largest weight; `search._scored` calls it per stage (rel_err from the
two acceptance estimates), `print_report` prints it, and `coverage._rate` calls it for a cell
made only of a search's fresh stage (rel_err 0, labelled approximate). `coverage.wilson(k, n)`
already takes a non-integer n. sample-record.md, section 8, measured the delta-method
interval's coverage at 0.61 to 0.94 of its nominal 95 %.

1. **The bound at 0 failures** (exact, one-sided 95 %). `plain_estimate` gains keyword-only
   arguments, so its callers keep working: `cap`, the largest weight the proposal can give
   before the normaliser (1 / `defensive` from the stage's `g<t>.yaml`; 1 when the proposal
   is the base), and `z_q`, `m_q`, `z_b`, `m_b`, the two acceptance estimates and their draw
   counts. At 0 failures U = cap (Z_q upper / Z_b lower) (1 - 0.025^(1/n)), the acceptances
   by Clopper-Pearson at 0.0125 each (beta quantiles, no scipy); the interval is [0, U],
   `interval_exact` true, and `interval_method` names the bound and the split (0.025, 0.0125,
   0.0125). Without counts (coverage's path) the normaliser is taken as exact, and the method
   says so. By hand: n 1000, beta 0.1, no constraints: U 3.68e-2.
2. **At 1 failure or more,** a Wilson score interval on Kish's n_eff and the weighted p,
   `wilson(p n_eff, n_eff)`, moved to one shared place rather than copied; its ends widened by
   the two acceptance ratios the same Bonferroni way (Wilson at 0.025 a side, the ratios at
   0.0125). Labelled approximate, `interval_exact` false. One rule from 1 failure up, no
   switch to the normal interval, which stays in the record as `interval_normal` for
   comparison only.
3. **Measured before it is trusted.** Wilson on n_eff's empirical coverage on test_coverage's
   rare-event harness (the one behind section 8's table), at the same weight settings,
   recorded beside the delta method's 0.61 to 0.94. It stays labelled approximate whatever
   comes out; if it covers worse than the delta method at any setting, the work stops and goes
   to 133 before any landing.
4. **The report.** `print_report` prints "failures k of n" before the rate, then the interval
   and its method; the generation lines are unchanged; coverage shows the method as now.
   sample-record.md and 092's K11 text get a line each on what the record now holds.
5. **Tests** (test_search.py, test_coverage.py): the 0-failure bound against the closed form
   at n 1000 and beta 0.1, with and without constraints; U grows when the acceptance counts
   shrink (m 100 against 100000), so the normaliser's term is exercised and not only its
   limit (133); a base proposal gives cap 1; a few failures give the Wilson interval,
   labelled approximate; many failures with light weights give an interval within 10 % of the
   normal one; the record and the printed report name the method; callers without the new
   arguments still get a result.
6. **K13 step v read again.** `search report` on its output (`/var/tmp/aeon/k13v-search`)
   prints [0, 3.68e-2], exact; the search is not re-run.

**Amended 2026-11-25 (133), before the code: point 2 and its checks.** Wilson on Kish's n_eff is
dropped. The repo's own evidence is against it: coverage.py's weighted path once used Kish's
n_eff and its intervals were about 8 times too wide on a rare-event proposal (243), because a
rare-event proposal ties the weights to the failures; it was replaced with the delta method.
For the search's plain estimator the normal interval, p +- 1.96 se with se from the weighted
failure terms, already is the delta-method interval. So:

- **Point 2 becomes:** at k >= 1 failures the headline interval is the normal (delta) one,
  labelled approximate with its measured coverage (point 3), its ends widened by the
  normaliser's Bonferroni ratios, its lower end clipped at 0 as now.
- **Point 1 holds at every k** (133): U_k = cap (Z_q upper / Z_b lower) CP-upper(k of n) at
  ALPHA_F is a rigorous one-sided 95 % upper bound for any k, since p <= cap (Z_q / Z_b) q(F)
  holds whatever k is. At k >= 1 it is reported beside the headline as `upper_exact`; when the
  delta interval's upper end exceeds U_k, it is clipped there and the method says so. At k = 0
  the interval is [0, U_0], as before.
- **Point 3 becomes:** the delta interval's empirical coverage at 1 to 5 failures on
  test_coverage's rare-event harness, recorded here; and U_k's coverage in every seed of the
  same runs. U_k is a 95 % bound, so a miss is possible at up to 5 %; the cap makes it far
  looser than that, and every seed covering is the prediction.
- **Point 5 drops** the "within 10 % of the normal interval at many failures" test (there is
  no second interval to compare); it adds that U_k is reported at k >= 1 and clips the delta's
  upper end when that exceeds it.

Points 1, 4 and 6 as before. Point 1's code was begun before this amendment and is changed to
it before it is committed.

Out of scope: a tighter bound that uses where the failures lie; the generations' diagnostic
estimate.

## Point 3, measured (2026-11-25)

K11 check 1's rare event (base N(0, I) in 2-D, failure x1 + x2 > 5.2, p = 1.18e-4) under the
defensive mixture 0.1 base + 0.9 N(mu (1, 1), I), mu set so that 1000 draws hold about 1, 2, 3
and 5 failures; 2000 repetitions per setting, through `search.plain_estimate` (cap 10, the
normaliser exact). The delta (normal) interval's two-sided coverage of p among the repetitions
with a failure, the headline's over all of them (k = 0 gives [0, U_0]), and U_k's one-sided
coverage (`i183_coverage.py`, seeds 184, 185, 186 and 188):

| expected k | mu | mean k | share k = 0 | delta, k >= 1 | headline | U_k | clipped |
|---|---|---|---|---|---|---|---|
| 1 | 0.4346 | 1.02 | 0.355 | 1.000 | 1.000 | 1.000 | 0.000 |
| 2 | 0.5871 | 2.05 | 0.119 | 0.977 | 0.980 | 1.000 | 0.000 |
| 3 | 0.6807 | 2.96 | 0.047 | 0.919 | 0.922 | 1.000 | 0.000 |
| 5 | 0.8039 | 5.04 | 0.005 | 0.911 | 0.911 | 1.000 | 0.000 |

The delta interval covers 0.91 to 1.00 at 1 to 5 failures, within or above the 0.61 to 0.94
sample-record.md measured for the self-normalised delta interval, and it stays labelled
approximate. U_k covered p in all 8000 repetitions, as predicted; it was never below the
delta's upper end here, so nothing was clipped (the clipping is tested on a stated cap below
the weights). A seeded 200-repetition version of the 3-failure setting is in test_search.py.

**coverage.py** passes no cap (a record names its proposal by id only), so a cell made of a
search's fresh stage with no failure now has no interval, said so in its method, where it had
[0, 0]; its exposure-weighted overall refuses such a category by name. The bound is in the
search's report.
 Order: this plan (docs); the code and tests; point 3's measurement into this record;
local checks and a full gate; a landing request to 133.
