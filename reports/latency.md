## Latency and throughput

| Config | Rerank depth | Warm-up | N timed | Concurrency | p50 (s) | p95 (s) | Throughput (q/s) | D1 pass |
|---|---|---|---|---|---|---|---|---|
| fused-rerank | 50 | 10 | 170 | 1 | 1.0339 | 1.2104 | 0.97 | yes |

### Memory pressure (before / after each pass)

| Config | Swapins before->after | Swapouts before->after | Compressor pages before->after |
|---|---|---|---|
| fused-rerank | 3011978->3016009 | 3692751->3692751 | 141027->150320 |
