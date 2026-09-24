## Latency and throughput

| Config | Rerank depth | Warm-up | N timed | Concurrency | p50 (s) | p95 (s) | Throughput (q/s) | D1 pass |
|---|---|---|---|---|---|---|---|---|
| fused-rerank | 50 | 10 | 170 | 1 | 0.9905 | 1.1947 | 1.00 | yes |

### Memory pressure (before / after each pass)

| Config | Swapins before->after | Swapouts before->after | Compressor pages before->after |
|---|---|---|---|
| fused-rerank | 27123400->27174541 | 27738470->27812182 | 158242->187273 |
