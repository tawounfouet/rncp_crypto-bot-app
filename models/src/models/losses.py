"""Custom loss functions for LSTM training."""

from __future__ import annotations

import torch
import torch.nn.functional as F


class FocalLoss(torch.nn.Module):
    """Focal loss for multi-class classification.

    Downweights easy examples so training focuses on hard minority classes.
    Especially effective when HOLD dominates the label distribution.
    gamma=0 degrades to standard cross-entropy.
    """

    def __init__(self, gamma: float = 2.0, weight: torch.Tensor | None = None) -> None:
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(logits, targets, weight=self.weight, reduction="none")
        pt = torch.exp(-ce)
        return ((1 - pt) ** self.gamma * ce).mean()
