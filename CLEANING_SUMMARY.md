# Text Cleaning Pipeline - Quick Reference

## 📊 Pattern Analysis Results

| Pattern Type | Frequency | Risk Level | Action |
|-------------|-----------|------------|---------|
| Trailing spaces | 0% | - | ✅ Already clean |
| Multiple spaces | 0% | - | ✅ Already clean |
| Dotted signatures | 1% | Low | ✅ Remove |
| Date + signatures | ~10% | Low | ✅ Remove |
| Uppercase lines | ~30% | Low | ✅ Remove |
| Section headers | ~15% | Medium | ✅ Remove |
| Graph/table titles | 2% | Low | ✅ Remove |
| Chart labels | 2% | Medium | ✅ Remove |
| Rare symbols | 6% | Very low | ✅ Replace |
| Enumeration (a), 1), i)) | 44% | **HIGH** | ❌ **SKIP** |

---

## 🔄 Cleaning Pipeline (8 Steps - Conservative Approach)

```
Raw Text
   ↓
[1] Remove dotted signature lines
   ↓          (\n\n…………… WALDO MENDOZA → removed)
[2] Remove date + signature blocks
   ↓          (Lima, 23 de mayo... CONSEJO FISCAL → removed)
[3] Remove standalone uppercase lines
   ↓          (\n\nCONSEJO FISCAL DEL PERÚ\n\n → removed)
[4] Remove standalone section headers
   ↓          (\n\nConclusiones\n\n → removed)
[5] Remove graph/table titles
   ↓          (Gráfico 1: ... → removed)
[6] Remove chart labels
   ↓          ((A) Growth (B) Deficit → removed)
[7] Replace rare symbols
   ↓          (• → space, … → ...)
[8] Normalize whitespace
   ↓          (multiple spaces/newlines → normalized)
Clean Text (Ready for Segmentation)
```

---

## ⚠️ Why Skip Enumeration Removal (Step 9)?

**Enumeration patterns are MOSTLY LEGITIMATE content:**

❌ **Do NOT remove**:
- "...está condicionado a: **(i)** la evolución de la pandemia..."
- "...siguientes motivos: **1)** contrastan con la previsión..."
- "...establecen: **a)** la prohibición de crear o aumentar..."

These are **numbered points** that form part of the actual fiscal analysis text!

✅ **Only remove if**:
- Standalone pattern: `\n\na) \n\n` (no content)
- Confirmed chart label (handled in Step 6)

**Recommendation**: Skip Step 9 entirely to preserve content structure.

---

## 📋 Example: Before vs After

### **Before Cleaning**

```
...incidido en una fuerte contracción de los sectores vinculados al consumo privado.

Lima, 23 de mayo de 2022

CONSEJO FISCAL DEL PERÚ

Análisis de riesgos fiscales

El CF advierte que, en la actual situación macroeconómica y fiscal, se ha
incrementado el riesgo cambiario...

Gráfico 1: Evolución de la deuda pública
(A) Deuda bruta (B) Deuda neta

Conclusiones

El CF considera que las proyecciones macroeconómicas previstas en el IAPM
para 2021 son razonables: 1) son consistentes con la recuperación observada,
2) reflejan el efecto estadístico positivo...
```

### **After Cleaning**

```
...incidido en una fuerte contracción de los sectores vinculados al consumo privado.

El CF advierte que, en la actual situación macroeconómica y fiscal, se ha
incrementado el riesgo cambiario...

El CF considera que las proyecciones macroeconómicas previstas en el IAPM
para 2021 son razonables: 1) son consistentes con la recuperación observada,
2) reflejan el efecto estadístico positivo...
```

**Removed**:
- ✅ Date + signature: "Lima, 23 de mayo... CONSEJO FISCAL DEL PERÚ"
- ✅ Section headers: "Análisis de riesgos fiscales", "Conclusiones"
- ✅ Graph title: "Gráfico 1: ..."
- ✅ Chart labels: "(A) Deuda bruta (B) Deuda neta"

**Preserved**:
- ✅ Enumeration: "1) son consistentes..., 2) reflejan..."
- ✅ Paragraph structure
- ✅ Full sentences

---

## 🎯 Expected Outcomes

### **Quantitative Metrics**

- **Text reduction**: ~10-15% character reduction
- **Noise removal**: ~90% of non-content patterns removed
- **Content preserved**: ~99% of actual analysis text retained

### **Qualitative Improvements**

✅ **Removed**:
- Signatures and formal closings
- Administrative metadata (dates, names)
- Visual element titles (graphs, tables)
- Section headers without content
- Non-textual symbols

✅ **Preserved**:
- All substantive analysis paragraphs
- Numbered/lettered list items
- Sentence structure and coherence
- Technical terminology and acronyms

---

## 🚀 Implementation Plan

### **Phase 1: Development** (Current)
1. ✅ Analyze patterns in data
2. ✅ Design ordered cleaning pipeline
3. ⏳ Implement cleaning functions
4. ⏳ Write unit tests for each step

### **Phase 2: Validation**
1. Test on 20-30 sample records
2. Manual review of before/after
3. Measure metrics (char reduction, false positives)
4. Adjust patterns based on findings

### **Phase 3: Production**
1. Apply to full dataset (336 records)
2. Generate cleaning report (statistics per step)
3. Save cleaned text to new JSON file
4. Proceed to paragraph segmentation

---

## 🛡️ Risk Mitigation

| Risk | Mitigation Strategy |
|------|---------------------|
| Remove legitimate content | Require `\n\n` paragraph boundaries for all removals |
| Break sentence coherence | Skip enumeration removal (Step 9) |
| Remove acronyms | Uppercase removal requires ≥3 words |
| Remove mid-sentence text | All patterns check line start/boundaries |
| Over-aggressive cleaning | Start with conservative approach, iterate |

---

## 💡 Key Design Principles

1. **Order Matters**: Steps are sequenced to avoid pattern interference
2. **Conservative Default**: Skip high-risk operations by default
3. **Boundary Awareness**: Patterns require paragraph boundaries (`\n\n`)
4. **Preserve Structure**: Keep numbered lists and enumeration
5. **Validate Early**: Test on samples before full dataset

---

## 📝 Next Steps

Execute the implementation phase:

```bash
# Create cleaning functions
python text_cleaning.py --mode develop

# Test on samples
python text_cleaning.py --mode test --sample 20

# Apply to full dataset
python text_cleaning.py --mode production
```

See **TEXT_CLEANING_PLAN.md** for detailed pattern specifications and code structure.
