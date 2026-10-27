"""Validation-only Gaussian scale MLE; no test labels or model mutation."""
import math
from statistics import mean
from .financial_contract import finite
from .financial_evaluation import gaussian_scores


def fit_scale_calibration(mu, scale, targets):
    gaussian_scores(mu, scale, targets)  # shape and finite admission
    # Bounded multiplier avoids degenerate zero variance on small fixtures.
    rms = math.sqrt(mean(((y-m)/s)**2 for m, s, y in zip(mu, scale, targets)))
    multiplier = min(20., max(.05, rms))
    return {'version': 1, 'method': 'BOUNDED_GAUSSIAN_SCALE_MLE',
            'scale_multiplier': multiplier, 'fit_count': len(targets),
            'fit_partition': 'VALIDATION_ONLY', 'bounds': [.05, 20.]}


def calibrated_scores(mu, scale, targets, calibration):
    multiplier = finite(calibration['scale_multiplier'], 'scale multiplier')
    if not .05 <= multiplier <= 20.:
        raise ValueError('calibration multiplier bounds')
    return gaussian_scores(mu, [s*multiplier for s in scale], targets)
