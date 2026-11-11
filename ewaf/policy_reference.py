"""G18-A review guidance only; never parsed or consumed as scoring policy.

Source: Computation.docx supplied 2026-10-17, reconciled in
docs/g18-a-computation-crosswalk-2026-10-17.md. All approval decisions remain
pending regardless of recorded drafts, mathematical results or attestations.
"""
from dataclasses import dataclass


CRITERION_LABELS = {
    'SI': 'Socioeconomic Indicator',
    'ES': 'Employment Status',
    'PA': 'Previous Assistance Received',
    'ND': 'Number of Dependents',
    'PR': 'Program Relevance',
}


@dataclass(frozen=True)
class PolicyReviewItem:
    key: str
    title: str
    reference: str
    decision: str
    source: str
    status: str = 'Pending Association decision'


# Prose deliberately has no machine-consumable encodings, bounds or thresholds.
REVIEW_ITEMS = (
    PolicyReviewItem('authority', 'Source authority and scope',
        'Computation.docx is a reference. Its replacement of the workbook is not confirmed.',
        'Confirm draft or approved replacement, approving role, documentary authority, '
        'effective date, program scope, locking and permitted successor revisions.',
        'Handoff sections 3 and 7; OQ-09, OQ-26'),
    PolicyReviewItem('ahp', 'AHP judgments and arithmetic',
        'Both sources describe normalized-column row averages for five criteria, '
        'RI 1.12 and CR below 0.10. The document uses PA, SI, ES, ND, PR order; '
        'configuration entry uses SI, ES, PA, ND, PR. Match names, not positions.',
        'Approve actual judgments, comparison scale, precision and display policy. '
        'Use calculated weights, never rounded document coefficients. '
        'Consistency alone does not establish fairness or authorization.',
        'Computation.docx tables 1–8; workbook C3:G7, C29:C33, E63:E65; OQ-10, OQ-12'),
    PolicyReviewItem('SI', 'SI — Socioeconomic Indicator',
        'The document names SI but does not define its measure. The workbook uses sample monthly income.',
        'Define measure, individual or household basis, unit, period, range, evidence, '
        'expiry and direction. Higher income increases the workbook example; historical inverse wording conflicts.',
        'Computation.docx table 2; workbook C82, E92:E94; OQ-06, OQ-18, OQ-23'),
    PolicyReviewItem('ES', 'ES — Employment Status',
        'Proposed document encoding: Full-Time Worker 1; Part-Time Worker 2; '
        'Seasonal Worker 3; Unemployed 4. The workbook lists the same examples.',
        'Approve category definitions and coverage, evidence, expiry, encoding and direction. '
        'Unmapped, unknown, self-employed, unpaid-carer and unable-to-work cases need explicit handling.',
        'Computation.docx table 9; workbook D80:E83; OQ-07, OQ-23'),
    PolicyReviewItem('PA', 'PA — Previous Assistance Received',
        'The workbook example increases PA for more receipts. Current evidence distinguishes actual '
        'non-voided releases from selection or attendance.',
        'Define count or amount, included assistance types and programs, lookback, cutoff, '
        'void/reversal treatment, evidence and direction. No manual assistance counter.',
        'Computation.docx table 2; workbook C81, E101:E103; OQ-08, OQ-19, OQ-23'),
    PolicyReviewItem('ND', 'ND — Number of Dependents',
        'The document names ND. The workbook illustrates counts of 0, 2 and 5; these are not approved bounds.',
        'Define dependent and household, verification, expiry, integer range or cap and direction.',
        'Computation.docx table 2; workbook C84, E97:E99; OQ-07, OQ-11, OQ-23'),
    PolicyReviewItem('PR', 'PR — Program Relevance',
        'Proposed encoding: Not Aligned 1; Partially Aligned 2; Highly Aligned 3; Fully Aligned 4.',
        'Approve an evidence-backed program-specific rubric, item outcomes, aggregation, '
        'encoding and direction. Decide whether Not Aligned fails eligibility or is scoreable; '
        'a relevance score cannot override eligibility.',
        'Computation.docx table 10; workbook D85:E88; OQ-07, OQ-23'),
    PolicyReviewItem('evidence', 'Evidence and incomplete information',
        'Document encodings do not verify applicant declarations. G12 retains separate evidence reviews.',
        'Approve accepted evidence, reviewer duties, observation/expiry, disputes, accessible assessment '
        'and correction/revalidation. Missing information is not zero or automatic ineligibility.',
        'Handoff section 3; OQ-02, OQ-23, OQ-24'),
    PolicyReviewItem('normalization', 'Normalization and evaluation pool',
        'The document defines minimum and maximum within the dataset, with no inversion stated. '
        'G15 synthetic arithmetic requires explicit fixed bounds and benefit or inverse direction.',
        'Choose cohort-derived or fixed bounds explicitly, with each direction. Define the frozen '
        'full eligible pool, cutoff, all-equal ranges, missing values, outliers and full-pool recalculation.',
        'Computation.docx Min-Max Normalization; workbook C81:C85; OQ-11, OQ-18, OQ-19'),
    PolicyReviewItem('classification', 'Score scale and classification',
        'The weighted sum is 0–1; the source bands use 0–100. Printed bands are '
        '0–39.99 minimal, 40–59.99 low, 60–79.99 moderate and 80–100 high.',
        'Approve scale conversion and boundaries on unrounded scores. Candidate intervals '
        '0 ≤ s < 40, 40 ≤ s < 60, 60 ≤ s < 80, 80 ≤ s ≤ 100 avoid gaps, '
        'but remain a proposal. Do not round first to assign a band.',
        'Computation.docx table 11; workbook H86, F90:G93; OQ-12, OQ-25'),
    PolicyReviewItem('ranking', 'Ranking and human selection',
        'The document retains human validation. A score does not grant eligibility or assistance.',
        'Approve ranking direction, exact ties, capacity handling, selection rationale, exceptions, '
        'cutoff and repeat/supersession rules. Selection, publication and actual release stay separate.',
        'Computation.docx Human Validation; handoff section 3; OQ-13, OQ-15, OQ-22'),
    PolicyReviewItem('workflow', 'Membership and workflow conflicts',
        'The document mentions member accounts, PWD identification and EWS for eligibility validation.',
        'Preserve no member accounts, onsite membership and manual PRPWD; infer no universal '
        'PDAO-ID prerequisite. Membership, required evidence and eligibility must precede EWAF. '
        'Operational source currency and acceptance remain later increments.',
        'Handoff sections 4–5; DEC-024, DEC-027; OQ-16, OQ-27'),
)
