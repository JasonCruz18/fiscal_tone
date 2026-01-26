# Paragraph Detection Strategies for Raw Text Extraction

## Current Implementation

The `robust_scanned_extraction.py` currently uses **vertical spacing analysis** to insert `\n\n` markers. Here's how it works and alternative strategies you can consider.

---

## Strategy 1: Vertical Spacing Analysis (IMPLEMENTED)

**Method:** Analyze the vertical distance between consecutive OCR lines. When gap exceeds threshold, insert `\n\n`.

**Implementation:** (lines robust_scanned_extraction.py:275-332)
```python
def extract_text_with_paragraph_markers(image, lang='spa'):
    # Get OCR data with line positions
    ocr_data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)

    # Build lines with vertical positions
    lines = []  # Each line has: text, top, bottom

    # Detect vertical gaps between lines
    for line in lines:
        vertical_gap = current_line_top - previous_line_bottom

        if vertical_gap > THRESHOLD:  # e.g., 20 pixels
            insert "\n\n"
        else:
            insert "\n"
```

**Pros:**
- ✅ Language-independent
- ✅ Works well for visually separated paragraphs
- ✅ Handles tables and lists naturally (large gaps before/after)
- ✅ No false positives from text content

**Cons:**
- ❌ May miss paragraphs with minimal spacing
- ❌ Sensitive to OCR layout detection quality
- ❌ Threshold tuning required per document style

**Recommended threshold:** `20 pixels` at 300 DPI (adjustable via `PARAGRAPH_SPACING_THRESHOLD`)

---

## Strategy 2: Line-Ending Analysis (COMPLEMENTARY)

**Method:** Detect paragraph boundaries based on line endings and beginnings.

**Logic:**
```python
def is_paragraph_break(prev_line, curr_line):
    # Rule 1: Previous line ends with sentence-ending punctuation
    if prev_line.rstrip().endswith(('.', '!', '?', ':')):
        # Rule 2: Current line starts with capital letter
        if curr_line[0].isupper():
            return True

    # Rule 3: Short line (likely header) followed by regular text
    if len(prev_line.split()) <= 5:
        return True

    return False
```

**Pros:**
- ✅ Captures logical paragraph structure
- ✅ Works when visual spacing is minimal
- ✅ Language-aware (uses punctuation rules)

**Cons:**
- ❌ False positives on abbreviations (e.g., "Sr.", "Art.")
- ❌ Misses paragraphs starting mid-sentence
- ❌ Language-specific rules needed

**Recommendation:** Use as **complement** to vertical spacing for edge cases.

---

## Strategy 3: Hybrid Approach (RECOMMENDED FOR NEXT ITERATION)

**Method:** Combine vertical spacing (primary) with textual cues (validation).

**Algorithm:**
```python
def detect_paragraph_break(prev_line, curr_line, vertical_gap):
    # Primary: Large visual gap (high confidence)
    if vertical_gap > 25:
        return True

    # Secondary: Moderate gap + textual cues (medium confidence)
    if vertical_gap > 15:
        if prev_line.endswith('.') and curr_line[0].isupper():
            return True
        if is_section_header(curr_line):  # ALL CAPS, short, ends with ':'
            return True

    # Tertiary: Small gap but strong textual evidence
    if vertical_gap > 10:
        if curr_line.startswith('•') or curr_line.startswith('➢'):
            return True  # Bullet list item
        if re.match(r'^\d+\.', curr_line):
            return True  # Numbered list

    return False
```

**Pros:**
- ✅ Best of both worlds (visual + semantic)
- ✅ Adaptive to document styles
- ✅ Reduces false positives and negatives

**Cons:**
- ❌ More complex logic
- ❌ Requires more testing/tuning

---

## Strategy 4: Indentation Detection (ADVANCED)

**Method:** Detect paragraph starts by analyzing horizontal indentation of first word.

**How it works:**
```python
def detect_indentation(ocr_data):
    # Group words by line
    lines = group_by_line(ocr_data)

    # Find left margin of each line
    for line in lines:
        first_word_x = line['words'][0]['left']

        # New paragraph if indented or outdented significantly
        if abs(first_word_x - median_left_margin) > 30:
            return True
```

**Pros:**
- ✅ Very accurate for traditionally formatted documents
- ✅ Detects indented paragraphs that visual spacing misses

**Cons:**
- ❌ Not reliable if documents don't use indentation
- ❌ OCR word-level positioning can be noisy
- ❌ Doesn't work for justified text

**Recommendation:** **NOT recommended** for Fiscal Council documents (typically use spacing, not indentation).

---

## Strategy 5: Confidence-Based Line Merging (QUALITY CONTROL)

**Method:** Use OCR confidence scores to decide line continuation vs. paragraph breaks.

**Logic:**
```python
def should_merge_lines(prev_line, curr_line):
    # Low confidence on line-ending word suggests possible split
    last_word_conf = prev_line['words'][-1]['conf']

    if last_word_conf < 60:  # Low confidence
        # Check if merging creates valid word
        merged = prev_line['text'] + curr_line['text']
        if is_valid_spanish_word(merged):
            return True  # Merge, don't insert \n\n

    return False
```

**Pros:**
- ✅ Fixes OCR line-break errors
- ✅ Improves text quality

**Cons:**
- ❌ Requires word dictionary
- ❌ Complex logic
- ❌ Orthogonal to paragraph detection (more about cleaning)

**Recommendation:** Defer to **text cleaning stage**, not extraction stage.

---

## Comparison Table

| Strategy | Accuracy | Complexity | Performance | Language-Dependent |
|----------|----------|------------|-------------|-------------------|
| **Vertical Spacing** (current) | ⭐⭐⭐⭐ | Low | Fast | No |
| **Line-Ending Analysis** | ⭐⭐⭐ | Medium | Fast | Yes (Spanish) |
| **Hybrid Approach** | ⭐⭐⭐⭐⭐ | Medium | Fast | Minimal |
| **Indentation Detection** | ⭐⭐ | High | Medium | No |
| **Confidence-Based** | ⭐⭐⭐ | High | Slow | Yes (dictionary) |

---

## Recommended Approach for Your Project

### Phase 1: Current (Raw Extraction)
✅ **Vertical Spacing Analysis** with 20px threshold
→ Simple, fast, language-independent
→ Good enough for ~80-90% of paragraphs

### Phase 2: Text Cleaning (Next Stage)
Add **textual validation**:
- Merge lines ending with hyphens: `palabra- ción` → `palabración`
- Fix incomplete sentences
- Validate paragraph boundaries using punctuation

### Phase 3: Paragraph Segmentation (Final Stage)
Apply **hybrid rules**:
- Verify `\n\n` markers are at logical boundaries
- Split/merge paragraphs based on semantic analysis
- Handle special cases (lists, tables, quotes)

---

## Configuration Recommendations

For Fiscal Council documents, I recommend:

```python
# Vertical spacing thresholds (in pixels at 300 DPI)
PARAGRAPH_SPACING_THRESHOLD = 20    # Default for most documents
LARGE_GAP_THRESHOLD = 30            # Section breaks
SMALL_GAP_THRESHOLD = 10            # Line continuation

# Textual cues (for hybrid approach)
SENTENCE_ENDINGS = ('.', '!', '?', ':')
SECTION_HEADER_MAX_LENGTH = 50      # characters
LIST_MARKERS = ['•', '➢', '-', '▪']

# OCR confidence
MIN_LINE_CONFIDENCE = 30            # Skip very low confidence lines
```

### Tuning Guidelines:

1. **If too many `\n\n` (over-segmentation):**
   - Increase `PARAGRAPH_SPACING_THRESHOLD` to 25-30px
   - Add textual validation to reject false positives

2. **If too few `\n\n` (under-segmentation):**
   - Decrease `PARAGRAPH_SPACING_THRESHOLD` to 15px
   - Add textual cues for minimal-spacing paragraphs

3. **For mixed document styles:**
   - Use **adaptive thresholds** based on median line spacing
   - Calculate per-page statistics and adjust dynamically

---

## Testing Your Paragraph Detection

After extraction, validate with these metrics:

```python
# 1. Average paragraph length (should be 200-500 chars for reports)
avg_para_len = df['text'].str.split('\n\n').apply(lambda x: np.mean([len(p) for p in x]))

# 2. Paragraph count per page (typically 3-8 for dense text)
para_per_page = df['text'].str.count('\n\n') / df['pages_processed']

# 3. Visual inspection: Check first 5 paragraphs manually
for i, para in enumerate(df['text'].iloc[0].split('\n\n')[:5], 1):
    print(f"\n--- Paragraph {i} ---")
    print(para)
```

**Red flags:**
- ⚠️ Paragraphs < 50 characters (likely header fragments)
- ⚠️ Paragraphs > 1000 characters (likely missed breaks)
- ⚠️ Paragraphs ending mid-sentence (bad break detection)

---

## Example Output

**Good paragraph marking:**
```
El presente informe contiene la opinión colegiada del Consejo Fiscal (CF) sobre las
proyecciones contenidas en el Informe de Actualización de Proyecciones Macroeconómicas 2017.

\n\n

Escenario internacional y local

\n\n

El IAPM incorpora una mejora de las perspectivas para el escenario macroeconómico
internacional, en comparación a las que se publicaron en el Marco Macroeconómico
Multiannual 2017 – 2019.
```

**Bad paragraph marking (too aggressive):**
```
El presente informe contiene la opinión

\n\n

colegiada del Consejo Fiscal (CF) sobre las

\n\n

proyecciones contenidas en el Informe
```

---

## Implementation Roadmap

### ✅ Done (Current)
- Basic vertical spacing analysis
- Fixed 20px threshold
- Line-by-line grouping

### 🔄 Next Steps (Optional Improvements)
1. Add textual validation for ambiguous gaps (15-25px range)
2. Detect section headers and force `\n\n` before them
3. Special handling for bullet lists (always start new paragraph)
4. Adaptive threshold based on document's median line spacing

### 🔮 Future (Advanced)
1. Machine learning-based paragraph classification
2. Context-aware boundary detection (using surrounding text)
3. Document structure analysis (introduction, body, conclusion)

---

## Summary

**Your current implementation is solid for Phase 1.** The vertical spacing approach will capture most paragraph boundaries correctly. For the 10-20% of edge cases, you can refine in the cleaning/segmentation stages.

**My recommendation:**
1. **Keep current implementation** for raw extraction
2. **Test on 3-5 PDFs** and review paragraph quality manually
3. **Adjust `PARAGRAPH_SPACING_THRESHOLD`** if needed (currently 20px)
4. **Add textual validation** in Phase 2 (cleaning) if quality issues arise

The beauty of inserting `\n\n` during extraction is that you can always **post-process** in Python:
```python
# Example: Merge paragraphs that were incorrectly split
text = re.sub(r'([a-z])\n\n([a-z])', r'\1 \2', text)  # Merge if both lowercase

# Example: Split paragraphs that were missed
text = re.sub(r'(\.) ([A-Z])', r'.\n\n\2', text)  # Split at ". Capital"
```

Good luck with extraction! 🚀
