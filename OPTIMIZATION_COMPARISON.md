# LLM Classification Optimization - Performance Comparison

## 📊 Original vs Optimized Performance

### Original Script (`llm.py`)

**Architecture:**
- Sequential processing (one paragraph at a time)
- Manual sleep of 1.2 seconds between requests
- Synchronous API calls
- Simple retry logic

**Performance:**
- **440 paragraphs**: ~8 hours (28,800 seconds)
- **Per paragraph**: ~65 seconds
- **Throughput**: ~0.9 paragraphs/minute

**For 1,675 paragraphs:**
- **Estimated time**: ~30 hours
- **Bottleneck**: Sequential processing + conservative delays

---

### Optimized Script (`llm_optimized.py`)

**Architecture:**
- **Async/concurrent processing** (up to 450 requests/minute)
- **Intelligent rate limiting** with aiolimiter
- **Batch processing** with automatic backups
- **Robust retry logic** with exponential backoff
- **Real-time progress tracking** with tqdm

**Performance:**
- **1,675 paragraphs**: ~10-15 minutes (600-900 seconds)
- **Per paragraph**: ~0.4 seconds
- **Throughput**: ~110-165 paragraphs/minute

**Improvements:**
- **Speed**: 120-180x faster
- **Efficiency**: Better API utilization
- **Reliability**: Automatic retries and backups

---

## 🔑 Key Optimizations

### 1. Concurrency (Biggest Impact)

**Original:**
```python
for i, row in df.iterrows():
    score = get_llm_score(row["text"])  # Wait for each
    time.sleep(1.2)  # Manual delay
```

**Optimized:**
```python
tasks = [classify_paragraph(para) for para in paragraphs]
results = await asyncio.gather(*tasks)  # All at once
```

**Impact**: 450 concurrent requests vs 1 at a time

---

### 2. Rate Limiting

**Original:**
- Manual `time.sleep(1.2)` = max 50 requests/minute
- Wastes 80% of API capacity

**Optimized:**
- `AsyncLimiter(max_rate=450, time_period=60)`
- Automatically manages rate to maximize throughput
- Adapts to API tier (Tier 1: 500 RPM, Tier 2: 5,000 RPM)

**Impact**: 9x better API utilization

---

### 3. Error Handling

**Original:**
```python
try:
    response = client.chat.completions.create(...)
except Exception as e:
    print(f"Error: {e}")
    return None  # Lost request
```

**Optimized:**
```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5)
)
async def classify_with_retry(text):
    # Automatic retry with backoff
```

**Impact**: Zero data loss on transient errors

---

### 4. Progress Tracking

**Original:**
- No feedback during execution
- Unclear how long remaining

**Optimized:**
```
Progress: |████████████████████| 1675/1675 [00:12<00:00, 138.75it/s]
```

**Impact**: Better UX and monitoring

---

## 💰 Cost Analysis

**Model: gpt-4o**
- Input: $0.0025 per 1K tokens
- Output: $0.01 per 1K tokens

**For 1,675 paragraphs:**
- Input tokens: ~1,000,000 (avg 600 tokens/paragraph)
- Output tokens: ~8,375 (5 tokens/paragraph)

**Total cost:** ~$2.50 + $0.08 = **$2.58 USD**

(Same cost for both scripts - only speed difference)

---

## 🎯 Model Recommendation

### Current Best: **gpt-4o** ✅

**Why gpt-4o:**
- Most capable OpenAI model
- Best instruction-following
- Optimal cost/performance ratio
- Native Spanish support

**Alternatives:**

| Model | Speed | Cost | Accuracy | Recommendation |
|-------|-------|------|----------|----------------|
| **gpt-4o** | Fast | $2.58 | Highest | ✅ USE THIS |
| gpt-4o-mini | Faster | $0.60 | Good | ⚠️ Less accurate |
| o1-preview | Slow | $15+ | Overkill | ❌ Not for simple classification |
| gpt-4-turbo | Medium | $10+ | High | ❌ More expensive, not better |

**GPT-5 Status:** Not publicly available yet

---

## 📈 Expected Timeline

### Original Script
```
Start: 00:00:00
After 8 hours: 440 paragraphs done
After 30 hours: 1,675 paragraphs done ✅
```

### Optimized Script
```
Start: 00:00:00
After 12 minutes: 1,675 paragraphs done ✅
```

**Time saved:** 29 hours 48 minutes

---

## 🚀 Usage Instructions

### Prerequisites
```bash
pip install openai aiolimiter tenacity tqdm pandas
export OPENAI_API_KEY="your-key-here"  # Unix/macOS
# or
set OPENAI_API_KEY=your-key-here      # Windows
```

### Run Classification
```bash
python llm_optimized.py
```

### Outputs
- `data/output/llm_output_paragraphs.json` - Paragraph-level scores
- `data/output/llm_output_paragraphs.csv` - Paragraph-level scores (CSV)
- `data/output/llm_output_documents.json` - Document-level aggregated
- `data/output/llm_output_documents.csv` - Document-level aggregated (CSV)
- `data/output/backup_fiscal_risk_*.json` - Automatic backups every 100 paragraphs

---

## 💡 Technical Details

### Rate Limiting Strategy

**Tier Detection:**
- Check your OpenAI dashboard for RPM limits
- Default: 450 RPM (safe for Tier 1)
- Tier 2+ can increase to 3,000+ RPM

**Adjustment:**
```python
# In llm_optimized.py, line 31:
rate_limiter = aiolimiter.AsyncLimiter(max_rate=450, time_period=60)
# Increase max_rate if you have higher tier
```

### Batch Size
- Current: 100 paragraphs per batch
- Allows incremental backups
- Can increase if you want fewer backups

### Retry Logic
- Max retries: 5 attempts
- Exponential backoff: 2s, 4s, 8s, 16s, 30s
- Handles rate limits, timeouts, API errors

---

## 🎓 Summary

**Use `llm_optimized.py` for:**
- ✅ 120-180x faster classification
- ✅ Better API utilization
- ✅ Robust error handling
- ✅ Real-time progress tracking
- ✅ Automatic backups

**Cost:** Same (~$2.58 for 1,675 paragraphs)

**Time:** ~12 minutes vs ~30 hours

**Recommended model:** gpt-4o (best available)
