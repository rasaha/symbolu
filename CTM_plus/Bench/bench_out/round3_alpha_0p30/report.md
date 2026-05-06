| Workload | Policy | Tier config | HBM hit rate | Slow-tier bytes/token | Avg access latency |
|---|---|---|---:|---:|---:|
| agentic_64k | ctm_plus | hbm_ddr_nvme | 99.7% | 148,736 B | 3,361 ns |
| agentic_64k | fifo | hbm_ddr_nvme | 99.7% | 127,488 B | 3,334 ns |
| agentic_64k | lru | hbm_ddr_nvme | 99.7% | 127,488 B | 3,334 ns |
| agentic_clustered_64k | ctm_plus | hbm_ddr_nvme | 100.0% | 3,456 B | 3,155 ns |
| agentic_clustered_64k | fifo | hbm_ddr_nvme | 100.0% | 3,072 B | 3,154 ns |
| agentic_clustered_64k | lru | hbm_ddr_nvme | 100.0% | 3,072 B | 3,154 ns |
| chat_32k | ctm_plus | hbm_ddr_nvme | 100.0% | 16,384 B | 2,066 ns |
| chat_32k | fifo | hbm_ddr_nvme | 100.0% | 16,384 B | 2,066 ns |
| chat_32k | lru | hbm_ddr_nvme | 100.0% | 16,384 B | 2,066 ns |
| rag_128k | ctm_plus | hbm_ddr_nvme | 100.0% | 0 B | 3,669 ns |
| rag_128k | fifo | hbm_ddr_nvme | 100.0% | 1,024 B | 3,669 ns |
| rag_128k | lru | hbm_ddr_nvme | 100.0% | 1,024 B | 3,669 ns |
