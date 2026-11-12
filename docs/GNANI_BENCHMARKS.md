# Gnani Indic Benchmark Corpus

## 1. Corpus Design
The Indic Speech Lab provides a reproducible, 8-item benchmark dataset located in `backend/app/indic/benchmarks.py`. Each test case targets a specific linguistic failure mode common in Indian voice AI deployments.

---

## 2. Benchmark Items Specification

| ID | Language | Category | Target Challenges |
|---|---|---|---|
| `indic-hi-banking-01` | `hi-IN` | Banking & Currency | Currency values (`₹५,०००`), account numbers (`४५६७`), IFSC code entities |
| `indic-hinglish-support-01` | `hi-IN` | Hinglish Code-Switching | Mixed Latin/Devanagari (`मेरा refund initiate नहीं हुआ`), loanwords (`refund`, `transaction ID`) |
| `indic-ta-railway-01` | `ta-IN` | Transit & Time | Tamil script, 24-hr time representations, train name entities |
| `indic-te-commerce-01` | `te-IN` | E-commerce Delivery | Telugu address entities, pin codes, delivery dates |
| `indic-bn-support-01` | `bn-IN` | Customer Care | Bengali script, billing terminology, account credentials |
| `indic-kn-telecom-01` | `kn-IN` | Telecom Recharge | Kannada script, numeric recharge amounts, validity periods |
| `indic-mr-gov-01` | `mr-IN` | Citizen Services | Marathi administrative terminology, application numbers |
| `indic-code-switch-dense` | `hi-IN` | Heavy Code-Switching | 50%+ Latin character density, technical jargon (`API key`, `dashboard`, `verify`) |

---

## 3. Benchmark Execution API
Automated benchmarking can be triggered via `POST /api/v1/indic/evaluate`:
```bash
curl -X POST http://localhost:8001/api/v1/indic/evaluate \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "reference": "मेरा ₹५,००० का refund initiate नहीं हुआ है",
    "hypothesis": "मेरा 5000 का refund initiate नहीं हुआ है",
    "expected_loanwords": ["refund", "initiate"]
  }'
```

Output:
```json
{
  "raw_wer": 0.2857,
  "raw_cer": 0.0811,
  "normalized_wer": 0.0,
  "normalized_cer": 0.0,
  "code_switch_ratio": 0.3846,
  "loanword_accuracy": 1.0,
  "details": {
    "norm_substitutions": 0,
    "norm_deletions": 0,
    "norm_insertions": 0
  }
}
```
*(Demonstrating that the apparent 28.5% WER was purely a numeral formatting artifact, cleanly resolved to 0.0% normalized WER).*

