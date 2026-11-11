"""Private presentation of already validated results; never assigns business rank."""
from decimal import Decimal

from .four_policy import CRITERIA


def ordered_results(results):
    # Compare Decimal values directly. Negation/rounding under the caller's
    # decimal context can erase distinctions in the retained 50-digit scores.
    rows = sorted(results, key=lambda row: Decimal(row.calculation['score_0_100']), reverse=True)
    for row in rows:
        traces = {trace.criterion: trace for trace in row.traces.all()}
        row.review_traces = [traces[code] for code in CRITERIA]
    return rows
