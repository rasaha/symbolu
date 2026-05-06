| Workload | Policy | Tier config | HBM hit rate | Slow-tier bytes/token | Avg access latency |
|---|---|---|---:|---:|---:|
| agentic_64k | ctm_plus | hbm_ddr_nvme | 100.0% | 9,088 B | 2,774 ns |
| agentic_64k | fifo | hbm_ddr_nvme | 100.0% | 0 B | 2,763 ns |
| agentic_64k | lru | hbm_ddr_nvme | 100.0% | 0 B | 2,763 ns |
| chat_32k | ctm_plus | hbm_ddr_nvme | 100.0% | 0 B | 2,001 ns |
| chat_32k | fifo | hbm_ddr_nvme | 100.0% | 0 B | 2,001 ns |
| chat_32k | lru | hbm_ddr_nvme | 100.0% | 0 B | 2,001 ns |
| rag_128k | ctm_plus | hbm_ddr_nvme | 100.0% | 0 B | 3,104 ns |
| rag_128k | fifo | hbm_ddr_nvme | 100.0% | 1,024 B | 3,104 ns |
| rag_128k | lru | hbm_ddr_nvme | 100.0% | 1,024 B | 3,104 ns |
