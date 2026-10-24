"""Deterministic, dependency-free research baselines.

These models are controls, not AlphaFold/Evoformer implementations.
"""
from __future__ import annotations
from math import isfinite

def _matrix(X):
    rows = [tuple(row) for row in X]
    if not rows or not rows[0]:
        raise ValueError("empty feature matrix")
    width = len(rows[0])
    if any(len(row) != width or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v) for v in row) for row in rows):
        raise ValueError("invalid feature matrix")
    return rows

class MeanReturnBaseline:
    def fit(self, X, y):
        rows = _matrix(X)
        values = list(y)
        if len(rows) != len(values) or any(not isfinite(v) for v in values):
            raise ValueError("invalid targets")
        self.width = len(rows[0])
        self.value = sum(values) / len(values)
        return self

    def predict(self, X):
        if not hasattr(self, "value"):
            raise ValueError("model not fitted")
        rows = _matrix(X)
        if len(rows[0]) != self.width:
            raise ValueError("feature schema mismatch")
        return [self.value] * len(rows)

class RidgeBaseline:
    """Train-only standardized ridge regression via deterministic gradient descent."""
    def __init__(self, penalty=1., steps=500, learning_rate=.05):
        if not isfinite(penalty) or penalty < 0 or not isinstance(steps, int) or steps < 1 or not isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("invalid ridge configuration")
        self.penalty, self.steps, self.learning_rate = penalty, steps, learning_rate

    def fit(self, X, y):
        rows = _matrix(X)
        target = list(y)
        if len(target) != len(rows) or any(not isinstance(v, (int, float)) or not isfinite(v) for v in target):
            raise ValueError("invalid targets")
        n, d = len(rows), len(rows[0])
        self.center = [sum(row[j] for row in rows) / n for j in range(d)]
        self.scale = [max(1., max(abs(row[j] - self.center[j]) for row in rows)) for j in range(d)]
        standardized = [tuple((row[j] - self.center[j]) / self.scale[j] for j in range(d)) for row in rows]
        self.intercept = sum(target) / n
        self.weights = [0.] * d
        for _ in range(self.steps):
            errors = [self.intercept + sum(w * x for w, x in zip(self.weights, row)) - t
                      for row, t in zip(standardized, target)]
            bias_grad = sum(errors) / n
            gradients = [sum(errors[i] * standardized[i][j] for i in range(n)) / n
                         + self.penalty * self.weights[j] for j in range(d)]
            self.intercept -= self.learning_rate * bias_grad
            self.weights = [w - self.learning_rate * g for w, g in zip(self.weights, gradients)]
            if not isfinite(self.intercept) or any(not isfinite(w) for w in self.weights):
                raise ValueError("ridge optimization diverged")
        return self

    def predict(self, X):
        if not hasattr(self, "weights"):
            raise ValueError("model not fitted")
        rows = _matrix(X)
        if len(rows[0]) != len(self.weights):
            raise ValueError("feature schema mismatch")
        return [self.intercept + sum(self.weights[j] * (row[j] - self.center[j]) / self.scale[j]
                                     for j in range(len(self.weights))) for row in rows]
