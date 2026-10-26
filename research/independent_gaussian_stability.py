"""Independent Gaussian NLL stability oracle for extreme standardized residuals."""
import math

def stable_gaussian_nll(mu, sigma, target):
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (mu,sigma,target)) or sigma <= 0:
        raise ValueError("invalid Gaussian parameters")
    residual = (target-mu)/sigma
    if not math.isfinite(residual):
        raise ValueError("standardized residual overflow")
    square = residual*residual
    if not math.isfinite(square):
        raise ValueError("Gaussian square overflow")
    loss = math.log(sigma) + .5*square + .5*math.log(2*math.pi)
    if not math.isfinite(loss):
        raise ValueError("Gaussian loss overflow")
    return loss
