## Criterion 1: per-configuration metrics

| Config | Category | recall@5 | recall@10 | ndcg@10 | mrr |
|---|---|---|---|---|---|
| bm25 | exact-term | 1.0000 | 1.0000 | 0.9772 | 0.9694 |
| bm25 | paraphrase | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| bm25 | multi-hop-relational | 0.7167 | 0.9000 | 0.7731 | 0.8817 |
| bm25 | pooled | 0.5722 | 0.6333 | 0.5834 | 0.6170 |
| dense | exact-term | 0.9167 | 0.9333 | 0.8953 | 0.8835 |
| dense | paraphrase | 0.7833 | 0.9333 | 0.6772 | 0.5975 |
| dense | multi-hop-relational | 0.9250 | 0.9500 | 0.9229 | 0.9875 |
| dense | pooled | 0.8750 | 0.9389 | 0.8318 | 0.8228 |
| fused | exact-term | 0.9333 | 0.9667 | 0.8064 | 0.7546 |
| fused | paraphrase | 0.0333 | 0.0500 | 0.0205 | 0.0116 |
| fused | multi-hop-relational | 0.6667 | 0.8917 | 0.7199 | 0.7526 |
| fused | pooled | 0.5444 | 0.6361 | 0.5156 | 0.5062 |
| fused-rerank | exact-term | 1.0000 | 1.0000 | 0.9905 | 0.9875 |
| fused-rerank | paraphrase | 0.7000 | 0.8500 | 0.5837 | 0.5015 |
| fused-rerank | multi-hop-relational | 0.8917 | 0.9750 | 0.9116 | 0.9806 |
| fused-rerank | pooled | 0.8639 | 0.9417 | 0.8286 | 0.8232 |

## Criterion 2: fused-rerank vs best single-method baseline

| Category | Metric | Baseline | Baseline value | Target value | Diff | 95% CI | Excludes zero |
|---|---|---|---|---|---|---|---|
| exact-term | recall@5 | bm25 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | recall@10 | bm25 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | ndcg@10 | bm25 | 0.9772 | 0.9905 | +0.0133 | [-0.0190, 0.0456] | no |
| exact-term | mrr | bm25 | 0.9694 | 0.9875 | +0.0181 | [-0.0250, 0.0639] | no |
| paraphrase | recall@5 | dense | 0.7833 | 0.7000 | -0.0833 | [-0.1833, 0.0167] | no |
| paraphrase | recall@10 | dense | 0.9333 | 0.8500 | -0.0833 | [-0.1833, 0.0000] | no |
| paraphrase | ndcg@10 | dense | 0.6772 | 0.5837 | -0.0934 | [-0.1781, -0.0161] | yes |
| paraphrase | mrr | dense | 0.5975 | 0.5015 | -0.0959 | [-0.1897, 0.0020] | no |
| multi-hop-relational | recall@5 | dense | 0.9250 | 0.8917 | -0.0333 | [-0.0917, 0.0250] | no |
| multi-hop-relational | recall@10 | dense | 0.9500 | 0.9750 | +0.0250 | [-0.0083, 0.0667] | no |
| multi-hop-relational | ndcg@10 | dense | 0.9229 | 0.9116 | -0.0113 | [-0.0418, 0.0185] | no |
| multi-hop-relational | mrr | dense | 0.9875 | 0.9806 | -0.0069 | [-0.0445, 0.0292] | no |
| pooled | recall@5 | dense | 0.8750 | 0.8639 | -0.0111 | [-0.0611, 0.0361] | no |
| pooled | recall@10 | dense | 0.9389 | 0.9417 | +0.0028 | [-0.0361, 0.0444] | no |
| pooled | ndcg@10 | dense | 0.8318 | 0.8286 | -0.0032 | [-0.0418, 0.0346] | no |
| pooled | mrr | dense | 0.8228 | 0.8232 | +0.0004 | [-0.0408, 0.0468] | no |
