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
| fused-rerank-ft | exact-term | 1.0000 | 1.0000 | 0.9528 | 0.9372 |
| fused-rerank-ft | paraphrase | 0.6000 | 0.7333 | 0.5260 | 0.4616 |
| fused-rerank-ft | multi-hop-relational | 0.9583 | 0.9833 | 0.9364 | 0.9722 |
| fused-rerank-ft | pooled | 0.8528 | 0.9056 | 0.8051 | 0.7903 |

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

## Before/after: fine-tuned cross-encoder vs pretrained

`after` = `fused-rerank-ft` (models/ce-braid), `before` = `fused-rerank` (cross-encoder/ms-marco-MiniLM-L-6-v2). Both rerank the identical `fused` top-50 candidate list. A positive diff means the fine-tuned model scores higher; a null or negative result is reported at the same prominence as a positive one.

| Category | Metric | Before (pretrained) | After (fine-tuned) | Diff | 95% CI | Excludes zero |
|----------|--------|--------------------:|-------------------:|-----:|--------|:-------------:|
| exact-term | recall@5 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | recall@10 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | ndcg@10 | 0.9905 | 0.9528 | -0.0377 | [-0.0741, -0.0083] | yes |
| exact-term | mrr | 0.9875 | 0.9372 | -0.0503 | [-0.0961, -0.0119] | yes |
| paraphrase | recall@5 | 0.7000 | 0.6000 | -0.1000 | [-0.2333, 0.0333] | no |
| paraphrase | recall@10 | 0.8500 | 0.7333 | -0.1167 | [-0.2167, -0.0167] | yes |
| paraphrase | ndcg@10 | 0.5837 | 0.5260 | -0.0577 | [-0.1470, 0.0409] | no |
| paraphrase | mrr | 0.5015 | 0.4616 | -0.0400 | [-0.1530, 0.0675] | no |
| multi-hop-relational | recall@5 | 0.8917 | 0.9583 | +0.0667 | [0.0167, 0.1250] | yes |
| multi-hop-relational | recall@10 | 0.9750 | 0.9833 | +0.0083 | [0.0000, 0.0250] | no |
| multi-hop-relational | ndcg@10 | 0.9116 | 0.9364 | +0.0248 | [0.0002, 0.0490] | yes |
| multi-hop-relational | mrr | 0.9806 | 0.9722 | -0.0083 | [-0.0335, 0.0250] | no |
| pooled | recall@5 | 0.8639 | 0.8528 | -0.0111 | [-0.0611, 0.0333] | no |
| pooled | recall@10 | 0.9417 | 0.9056 | -0.0361 | [-0.0750, -0.0028] | yes |
| pooled | ndcg@10 | 0.8286 | 0.8051 | -0.0236 | [-0.0613, 0.0093] | no |
| pooled | mrr | 0.8232 | 0.7903 | -0.0329 | [-0.0727, 0.0069] | no |
