# Text Cleaning Plan for Scanned PDFs

## Analysis Summary

Based on analysis of 336 extracted text records from scanned PDFs:

- **Average words per record**: 396.8
- **Min words**: 36, **Max words**: 703
- **No trailing spaces** or multiple consecutive spaces (already clean)
- **Key noise patterns identified**: Signatures, dates, graph/table titles, rare symbols, section headers

---

## Ordered Cleaning Steps

**IMPORTANT**: The order of these steps is critical. Each step is designed to NOT interfere with subsequent pattern matching.

### **Step 1: Remove Dotted Signature Lines**
**Why first**: These lines contain both dots and text (names), which could interfere with other pattern matching.

**Pattern**: Lines with 5+ consecutive dots followed by uppercase names
**Example**: `\n\n………………………………………………………….. WALDO EPIFANIO MENDOZA BELLIDO Presidente`

```python
# Pattern: 5+ dots/ellipsis followed by optional spaces and uppercase text
pattern = r'\n*[\.…]{5,}[\s\n]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)'
```

**Frequency**: 1% of records
**Risk**: Low (very specific pattern)

---

### **Step 2: Remove Date + Signature Blocks**
**Why second**: Complete signature blocks need to be removed before individual component patterns.

**Pattern**: Lima date followed by all-uppercase organization/name
**Examples**:
- `\n\nLima, 23 de mayo de 2022\n\nCONSEJO FISCAL DEL PERÚ`
- `\n\nLima, 15 de agosto de 2019\n\nWALDO MENDOZA BELLIDO`

```python
# Pattern: Lima date + newlines + uppercase text (3+ words)
pattern = r'\n*Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}[\s\n]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,})'
```

**Frequency**: ~10% of records
**Risk**: Low (very specific pattern with date + uppercase)

---

### **Step 3: Remove Standalone All-Uppercase Lines**
**Why third**: After removing signature blocks, catch remaining standalone uppercase lines.

**Pattern**: Lines with 3+ consecutive uppercase words
**Examples**:
- `\n\nCONSEJO FISCAL DEL PERÚ\n\n`
- `\n\nWALDO EPIFANIO MENDOZA BELLIDO\n\n`

**Conditions**:
- ≥3 consecutive uppercase words
- Surrounded by `\n\n` (paragraph boundaries)
- Exclude acronyms in parentheses like `(PBI)`, `(MEF)`

```python
# Pattern: Standalone line with 3+ uppercase words
# Must be surrounded by paragraph breaks (\n\n)
pattern = r'\n\n([A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+){2,})\n\n'
```

**Frequency**: ~30% of records have "CONSEJO FISCAL DEL PERÚ"
**Risk**: Low (requires standalone line + multiple uppercase words)

---

###**Step 4: Remove Standalone Section Headers**
**Why fourth**: After removing signatures, remove short section titles without ending punctuation.

**Pattern**: Short lines (< 50 chars, < 8 words) without ending period/colon
**Examples**:
- `\n\nAnálisis de riesgos fiscales\n\n`
- `\n\nConclusiones\n\n`
- `\n\nFinanzas públicas\n\n`

**Conditions**:
- Surrounded by `\n\n` (paragraph boundaries)
- Length: < 50 characters
- Word count: < 8 words
- Does NOT end with period (`.`), colon (`:`), or semicolon (`;`)
- Does NOT start with lowercase (avoids mid-sentence fragments)
- Exclude dates (already removed in Step 2)

```python
# Pattern: Short standalone line without ending punctuation
# Length < 50 chars, < 8 words, starts with uppercase
def is_section_header(line):
    line = line.strip()
    words = line.split()
    return (
        len(line) > 0 and len(line) < 50 and
        len(words) < 8 and
        line[0].isupper() and
        not line[-1] in '.;:' and
        not re.match(r'Lima,?\s+\d{1,2}\s+de', line)  # Not a date
    )
```

**Frequency**: ~15% of records
**Risk**: Medium (could remove legitimate short sentences - mitigated by requiring paragraph boundaries and uppercase start)

---

### **Step 5: Remove Graph/Table/Figure Titles**
**Why fifth**: These titles often appear with chart labels, which we'll handle separately.

**Pattern**: Lines starting with "Gráfico", "Tabla", "Cuadro", "Figura" + number
**Examples**:
- `\n\nGráfico 1: Leyes con impacto fiscal adverso\n\n`
- `\n\nTabla N° 1: escenarios de crecimiento 2020-2021\n\n`
- `\n\nGráfico N° 1: crecimiento económico 2020-2021\n\n`

**Conditions**:
- Starts with `Gráfico|Tabla|Cuadro|Figura` (case-insensitive)
- Followed by optional `N°`, `N°`, `#`, then number
- Remove entire line including description after colon

```python
# Pattern: Graph/Table title with number and optional description
pattern = r'\n*(Gráfico|Tabla|Cuadro|Figura)\s+N?°?\s*\d+[^\n]*\n*'
```

**Frequency**: 2% of records
**Risk**: Low (very specific pattern)

---

### **Step 6: Remove Chart Sub-Labels**
**Why sixth**: After removing main graph titles, remove chart panel labels.

**Pattern**: Lines like `(A)`, `(B)`, `A)`, `B)` followed by short descriptive text
**Examples**:
- `\n\n(A) Crecimiento del PBI 2020-2021 (B) PBI trimestral\n\n`
- `\n\nA) Leyes con impacto fiscal negativo B) Leyes con impacto fiscal por insistencia\n\n`

**Conditions**:
- Pattern: `(LETTER)` or `LETTER)` followed by text
- Multiple labels on same line (indicates chart labels, not list items)
- OR: Single label at start of very short line (< 60 chars)

```python
# Pattern: Chart labels - multiple labels on same line
# Example: (A) ... (B) ... or A) ... B) ...
pattern = r'\n*\([A-Z]\)[^\n]+\([A-Z]\)[^\n]*\n*'
pattern2 = r'\n*[A-Z]\)[^\n]+[A-Z]\)[^\n]*\n*'

# Pattern: Single chart label at start of short line
pattern3 = r'\n*\([A-Z]\)\s[^\n]{1,60}\n*'
```

**Frequency**: Rare (~2% of records)
**Risk**: Medium (could remove legitimate parenthetical notes - mitigated by requiring multiple labels or very short lines)

---

### **Step 7: Replace Rare Symbols with Spaces**
**Why seventh**: After structural cleaning, normalize symbols that don't affect pattern matching.

**Symbols to remove**:
- Bullet points: `•`, `➢`, `►`, `■`, `▪`
- Special characters: `Ø`
- Horizontal ellipsis: `…` (replace with `...`)

```python
# Replace symbols with space (to avoid word concatenation)
text = text.replace('•', ' ')
text = text.replace('➢', ' ')
text = text.replace('►', ' ')
text = text.replace('■', ' ')
text = text.replace('▪', ' ')
text = text.replace('Ø', ' ')
text = text.replace('…', '...')  # Normalize ellipsis
```

**Frequency**: ~6% of records
**Risk**: Very low (simple replacement)

---

### **Step 8: Normalize Whitespace**
**Why eighth**: After all pattern-based removal, clean up resulting whitespace artifacts.

**Actions**:
1. Replace multiple spaces with single space
2. Replace 3+ consecutive newlines with 2 newlines (preserve paragraph breaks)
3. Strip leading/trailing whitespace

```python
# Normalize multiple spaces to single space
text = re.sub(r' {2,}', ' ', text)

# Normalize excessive newlines (3+) to double newlines
text = re.sub(r'\n{3,}', '\n\n', text)

# Strip leading/trailing whitespace
text = text.strip()
```

**Frequency**: 100% of records (applies to all)
**Risk**: Very low (simple normalization)

---

### **Step 9: Remove Enumeration Patterns (OPTIONAL - Use with Caution)**
**Why last**: Enumeration patterns often represent legitimate list items.

**⚠️ RECOMMENDATION: SKIP THIS STEP**

Enumeration patterns like `a)`, `i)`, `1)` are **mostly legitimate list items** (found in 44% of records). Removing them would:
- Lose important structural information
- Potentially break sentence coherence
- Remove numbered points that are part of actual content

**Examples of LEGITIMATE enumeration (DO NOT REMOVE)**:
- "...está condicionado a: (i) la evolución de la pandemia..."
- "...siguientes motivos: 1) contrastan con la previsión..."
- "...establecen: a) la prohibición de crear o aumentar..."

**Only remove if**:
- Pattern is standalone (not part of sentence)
- Confirmed to be chart/figure label

**If you must remove enumeration**, use this conservative pattern:
```python
# ONLY remove standalone enumeration at line start
# Example: "\n\na) \n\n" or "\n\n1) \n\n"
pattern = r'\n\n([a-z]|[ivxIVX]+|\d+)\)\s*\n\n'
```

---

## Implementation Order Summary

```
1. Remove dotted signature lines          [Low risk, 1% frequency]
2. Remove date + signature blocks         [Low risk, 10% frequency]
3. Remove standalone uppercase lines       [Low risk, 30% frequency]
4. Remove standalone section headers      [Medium risk, 15% frequency]
5. Remove graph/table/figure titles       [Low risk, 2% frequency]
6. Remove chart sub-labels                [Medium risk, 2% frequency]
7. Replace rare symbols with spaces       [Very low risk, 6% frequency]
8. Normalize whitespace                   [Very low risk, 100% frequency]
9. Remove enumeration (SKIP RECOMMENDED)  [High risk, 44% frequency]
```

---

## Risk Mitigation Strategies

### **Conservative Approach (Recommended)**
- Execute Steps 1-8 only
- Skip Step 9 (enumeration removal)
- Preserve list structure and numbered points

### **Aggressive Approach (Higher Risk)**
- Execute all 9 steps
- May lose some legitimate content
- Better for downstream NLP tasks that don't need structure

### **Validation Strategy**
1. **Test on sample**: Run cleaning on 10-20 sample records
2. **Manual inspection**: Review before/after for each pattern
3. **Measure loss**: Track characters/words removed per step
4. **Iterate**: Adjust patterns based on false positives

---

## Edge Cases to Handle

### **1. Acronyms in Parentheses**
- `(PBI)`, `(MEF)`, `(SPP)` should NOT be removed
- **Solution**: Uppercase line removal requires ≥3 words

### **2. Mid-Sentence Patterns**
- "... opinión del CF, esto revela..." should NOT trigger removal
- **Solution**: All removal patterns require paragraph boundaries `\n\n`

### **3. Short Legitimate Sentences**
- "Dicha cantidad es significativa." (short but valid)
- **Solution**: Section header removal requires NO ending period

### **4. Numbered Sections**
- "1.2 Desempeño fiscal del SPNF:"
- **Solution**: Section header removal allows colons at end

---

## Next Steps

1. ✅ **Pattern Analysis Complete**
2. ⏳ **Implement cleaning functions** (current step)
3. ⏳ **Test on sample data** (20-30 records)
4. ⏳ **Validate results** (manual review)
5. ⏳ **Apply to full dataset** (336 records)
6. ⏳ **Prepare for paragraph segmentation**

---

## Code Structure Recommendation

```python
def clean_text_pipeline(text: str, aggressive: bool = False) -> str:
    """
    Execute ordered text cleaning pipeline

    Args:
        text: Raw extracted text
        aggressive: If True, includes Step 9 (enumeration removal)

    Returns:
        Cleaned text ready for paragraph segmentation
    """
    # Step 1: Remove dotted signature lines
    text = remove_dotted_signatures(text)

    # Step 2: Remove date + signature blocks
    text = remove_date_signature_blocks(text)

    # Step 3: Remove standalone uppercase lines
    text = remove_uppercase_lines(text)

    # Step 4: Remove standalone section headers
    text = remove_section_headers(text)

    # Step 5: Remove graph/table titles
    text = remove_graph_table_titles(text)

    # Step 6: Remove chart sub-labels
    text = remove_chart_labels(text)

    # Step 7: Replace rare symbols
    text = replace_rare_symbols(text)

    # Step 8: Normalize whitespace
    text = normalize_whitespace(text)

    # Step 9: Remove enumeration (optional, aggressive mode only)
    if aggressive:
        text = remove_enumeration(text)

    return text
```
