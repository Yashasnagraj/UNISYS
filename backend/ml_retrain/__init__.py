"""Continual-learning retrain package for the single-scan classifier.

Mirrors the layout of `ml_research/`: runnable as `python -m ml_retrain.retrain`.
The champion/challenger loop retrains ONLY the 25-feature single-scan model
(ortho_simulator/ml/model.pkl); the 22-feature longitudinal prognostic model in
ml_research/ is never touched.
"""
