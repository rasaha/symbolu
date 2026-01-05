======================================================================
PHASE-11B.2 STRUCTURAL ANALYSIS REPORT
======================================================================

## 1. STRUCTURAL CEILING OF DIFFERENTIATION
--------------------------------------------------
Total inputs tested: 500
Unique outputs produced: 250
Saturation ratio: 50.00%
PPV saturation point: 10
Family saturation point: Not reached

FINDING: Output space has high capacity - variations produce diverse outputs

## 2. OUTPUT CLUSTERING ANALYSIS
--------------------------------------------------
Family cluster strength: 0.900
PPV cluster strength: 0.960
Dominant clustering axis: BALANCED
Cross-entropy (family): 1.000
Cross-entropy (PPV): 1.000

FINDING: Outputs cluster more strongly by balanced than the other axis.

## 3. PPV DIMENSION CORRELATION ANALYSIS
--------------------------------------------------
Dimension impact scores (higher = more output variation):
  [0] edge_tension        : 0.714 ##############
  [1] edge_release        : 0.714 ##############
  [2] onset_sharpness     : 0.714 ##############
  [3] sonority_lift       : 0.714 ##############
  [4] continuity          : 0.714 ##############
  [5] discontinuity       : 0.714 ##############
  [6] rhythmic_impulse    : 0.714 ##############
  [7] stability_pressure  : 0.714 ##############

Strongest dimension: [0] edge_tension
Weakest dimension: [0] edge_tension

## 4. OPEN vs GOVERNED MODE COMPARISON
--------------------------------------------------
Total comparisons: 300
Divergence count: 0
Divergence rate: 0.00%
Output matches: 300
Template matches: 300
Trace content matches: 300

FINDING: MODE IDENTITY LOCK VERIFIED - Zero divergence between OPEN and GOVERNED

## 5. MINIMUM STRUCTURAL CHANGE DETECTION
--------------------------------------------------
Minimal PPV change for new hash: 2 unit(s)
Most sensitive dimension: [0] edge_tension
Family change alone produces new hash: True

FINDING: Requires 2+ unit change for new hash

## 6. SILENT COLLAPSE PATTERN DETECTION
--------------------------------------------------
Collapse detected: True
Collapse count: 200
Worst collapse size: 20
Collapse rate: 85.90%

WARNING: Silent collapse detected - multiple inputs produce identical outputs
This is EXPECTED due to canonicalization (by design, not a bug)

## 7. NEUTRAL BASELINE COMPARISON
--------------------------------------------------
Neutral unique outputs: 10
Structured unique outputs: 130
Neutral differentiation ratio: 100.00%
Structured differentiation ratio: 65.00%
Differentiation improvement: -35.00%

FINDING: Structured PPV variations do not improve differentiation

======================================================================
END OF REPORT
======================================================================