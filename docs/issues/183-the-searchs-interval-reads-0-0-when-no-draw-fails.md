# 183: the search's interval reads [0, 0] when no draw fails

**Status:** open; fix proposed, plan and code after 092 K13 lands (133, 2026-11-25).
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
