# ResoScan — Knowledge Graph & Causal Reasoning

The reasoning layer that explains *why* a verdict was reached, against similar prior cases — no black box.

## Why a graph

Fracture healing is inherently relational: a patient has scans over time, comorbidities, a fracture
context, and (eventually) a confirmed outcome. ResoScan builds an in-memory
[NetworkX](https://networkx.org) graph from the relational rows on each request (the cohort is small, so
this is trivially cheap and always current). Nothing here learns — it is deterministic retrieval and
rule-based explanation over stored features.

## Entities & relationships

- **Nodes:** `patient`, `scan`, `bone`, `fracture`, `comorbidity`, `outcome`, `cohort`
- **Edges:** `has_scan`, `has_comorbidity`, `of_bone`, `has_fracture`, `progressed_to`
  (scan → next scan), `confirmed_outcome`, `similar_to` (computed)

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/graph/patient/{id}` | Patient ego-graph (`nodes`, `edges`) for the UI |
| `GET /api/scans/{id}/similar?k=5` | Top-K most similar prior cases from **other** patients |
| `GET /api/scans/{id}/causal` | Active risk factors + a plain-language narrative |

## Similar-case retrieval (`services/knowledge_graph.py`)

A weighted z-score distance over a discriminative subset of the 25 signal features
(`SIMILARITY_FEATURE_WEIGHTS` — resonance, stiffness, damping lead), blended with comorbidity/context
overlap:

```
feature_sim   = 1 / (1 + weighted_zscore_distance)
comorb_overlap = Jaccard over {smoker, diabetic, bone, fracture_type}
score = 0.7 · feature_sim + 0.3 · comorb_overlap
```

Cases with a **confirmed outcome** are ranked first (a real prior result is worth more than a prediction).

## Causal layer (`services/causal.py`)

A **hand-coded clinical DAG** of the established drivers of healing rate — smoking, diabetes, age,
comminution, open/high-energy, late-week-low-TSI, implant-loosening — each edge carrying a **sign,
relative weight, and literature citation** (Scolaro 2014, Jiao 2015, Hak 2014, Marquez-Lara 2016,
Gustilo 1976, Tower 1993, Mattei 2021). `explain_verdict` returns the factors that are **active** for this
patient/scan and a narrative:

> *"Flagged Delayed Union because late week low tsi (week 16, TSI 43%) + smoker + comminuted, matching 5
> similar prior cases."*

This is not fitted — the edges encode domain priors, so the explanation is transparent and defensible.

## Roadmap

Full counterfactual **do-calculus** (DoWhy/EconML) and a **graph neural network** over the accumulated
graph (GraphSAGE/GAT) are deferred until there are 100+ real, outcome-labelled cases — a GNN on three
scans would be premature. See `docs/ROADMAP.md`.
