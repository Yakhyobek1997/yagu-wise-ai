"""Auralynq ModelFit Index — hardware-aware model selection and benchmarking for local RAG."""

from auralynq.modelfit.hardware import HardwareProfile, probe_hardware
from auralynq.modelfit.resource_estimator import ResourceEstimate, estimate_resources
from auralynq.modelfit.scoring import ModelFitScore, score_model

__all__ = [
    "HardwareProfile",
    "ModelFitScore",
    "ResourceEstimate",
    "estimate_resources",
    "probe_hardware",
    "score_model",
]
