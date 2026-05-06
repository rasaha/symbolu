| Workload | Policy | Tier config | HBM hit rate | Slow-tier bytes/token | Avg access latency |
|---|---|---|---:|---:|---:|
| agentic_64k | ctm_plus | hbm_hbf_nvme | 99.7% | 149,248 B | 3,469 ns |
| agentic_64k | fifo | hbm_hbf_nvme | 99.7% | 127,488 B | 3,448 ns |
| agentic_64k | lru | hbm_hbf_nvme | 99.7% | 127,488 B | 3,448 ns |
| chat_32k | ctm_plus | hbm_hbf_nvme | 100.0% | 16,896 B | 2,090 ns |
| chat_32k | fifo | hbm_hbf_nvme | 100.0% | 16,384 B | 2,090 ns |
| chat_32k | lru | hbm_hbf_nvme | 100.0% | 16,384 B | 2,090 ns |
| rag_128k | ctm_plus | hbm_hbf_nvme | 100.0% | 0 B | 3,880 ns |
| rag_128k | fifo | hbm_hbf_nvme | 100.0% | 1,024 B | 3,881 ns |
| rag_128k | lru | hbm_hbf_nvme | 100.0% | 1,024 B | 3,881 ns |
