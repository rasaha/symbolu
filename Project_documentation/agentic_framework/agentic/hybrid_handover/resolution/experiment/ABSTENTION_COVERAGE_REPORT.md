# Abstention & Coverage Report — Table 4 (hidden pilot)

Abstention treated as a decision problem (TA/FA/MA/TN) on the resolver-owned
cases; coverage is the answered fraction; selective accuracy is accuracy on
answered cases; unsafe = confident wrong answer where gold requires abstention.

| resolver | abst P | abst R | false-abst | missed-abst | coverage | selective | unsafe |
|---|---|---|---|---|---|---|---|
| frozen | — | 0.0000 | 0.0000 | 0.2667 | 1.0000 | 0.2833 | 1 |
| rule | — | 0.0000 | 0.0000 | 0.2667 | 1.0000 | 0.3333 | 2 |
| graph_traversal | — | 0.0000 | 0.0000 | 0.2667 | 1.0000 | 0.3333 | 2 |
| hybrid_relationship | 1.0000 | 0.1875 | 0.0000 | 0.2167 | 0.9500 | 0.2982 | 2 |

The hybrid abstains slightly more than GraphTraversal (coverage 0.95 vs 1.00) via
the confidence gate, which lowers its missed-abstention rate (0.2167 vs 0.2667)
but does not increase unsafe answers. Selective accuracy dips marginally — see the
non-inferiority report.
