# Robust Footer Detection Strategy

## Analysis Results from INFORME_N_002-2017-CF.pdf (7 pages)

### Consistent Pattern Discovered

After analyzing all pages with whitespace zone detection and blackness profiling:

**Every page has a LARGE whitespace zone in the bottom half (>100px) that represents the gap between main content and footer content.**

| Page | Largest WS Zone (bottom half) | Position | Size |
|------|-------------------------------|----------|------|
| 1 | Zone 27 | 2937-3065 (89.0%-92.9%) | 128px |
| 2 | Zone 37 | 2527-2783 (76.6%-84.3%) | 256px |
| 3 | Zone 33 | 2271-2485 (68.8%-75.3%) | 214px |
| 4 | Zone 43 | 2935-3060 (88.9%-92.7%) | 125px |
| 5 | Zone 47 | 2932-3058 (88.8%-92.7%) | 126px |
| 6 | Zone 42 | 2934-3058 (88.9%-92.7%) | 124px |
| 7 | Zone 27 | 2653-3058 (80.4%-92.7%) | 405px |

**Key Insight:** The footer separator line is at the **BOTTOM boundary** of this large whitespace zone (around 75-93%, varying by content length).

### False Positive: Address Line at 93-95%

The previous detector was finding lines at ~93-95% which is the **"Av. República de Panamá 3531"** address line, NOT the footer separator.

Evidence from analysis:
- Page 1: Zone 28 (93.7%-99.6%) contains address + final whitespace
- Page 2: Zone 40 (93.6%-99.6%) contains address + final whitespace
- All pages have consistent ~93-100% zone with address text

## New Robust Strategy

### Algorithm Steps

```
1. Start from PAGE MID (50%) to avoid institutional sign noise
2. Divide bottom half into rows, calculate blackness per row
3. Identify WHITESPACE ZONES (consecutive rows with <5% blackness, min 20px tall)
4. Find the LARGEST whitespace zone in 50-100% region
5. The footer separator line is at the BOTTOM of this zone
6. Verify by detecting horizontal line segments near this boundary (±20px)
7. Discard any lines in the 93-100% region (address area)
```

### Key Parameters

```python
PAGE_MID = 0.50                    # Start analysis from middle
WHITESPACE_THRESHOLD = 0.05        # <5% blackness = whitespace
MIN_ZONE_HEIGHT = 20               # Minimum 20px to count as zone
ADDRESS_REGION_START = 0.93        # Discard lines above 93% (address area)
FOOTER_SEARCH_MARGIN = 20          # Search ±20px around whitespace boundary
```

### Detection Logic

```python
def detect_footer_using_whitespace_zones(binary_image):
    height, width = binary_image.shape
    mid_y = int(height * 0.50)

    # 1. Calculate row-by-row blackness from mid to bottom
    row_blackness = []
    for y in range(mid_y, height):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append((y, blackness))

    # 2. Identify whitespace zones
    whitespace_zones = []
    in_zone = False
    zone_start = mid_y

    for y, blackness in row_blackness:
        if blackness < WHITESPACE_THRESHOLD and not in_zone:
            zone_start = y
            in_zone = True
        elif blackness >= WHITESPACE_THRESHOLD and in_zone:
            if y - zone_start >= MIN_ZONE_HEIGHT:
                whitespace_zones.append({
                    'start': zone_start,
                    'end': y,
                    'height': y - zone_start,
                    'position_pct': zone_start / height
                })
            in_zone = False

    # 3. Find LARGEST whitespace zone
    if not whitespace_zones:
        return int(height * 0.90), 'fallback'  # Fallback to 90%

    largest_zone = max(whitespace_zones, key=lambda z: z['height'])

    # 4. Footer separator is at BOTTOM of largest zone
    footer_candidate_y = largest_zone['end']

    # 5. Verify by detecting horizontal lines near this position
    search_start = max(mid_y, footer_candidate_y - FOOTER_SEARCH_MARGIN)
    search_end = min(height, footer_candidate_y + FOOTER_SEARCH_MARGIN)

    lines = detect_horizontal_lines_in_region(binary_image, search_start, search_end)

    # 6. Filter out address region lines (above 93%)
    address_threshold = int(height * ADDRESS_REGION_START)
    valid_lines = [l for l in lines if l['y'] < address_threshold]

    if valid_lines:
        # Select line closest to whitespace boundary
        footer_line = min(valid_lines, key=lambda l: abs(l['y'] - footer_candidate_y))
        return footer_line['y'], 'line_detected'
    else:
        # Use whitespace boundary directly
        return footer_candidate_y, 'whitespace_boundary'
```

### Validation Checks

1. **Discard address lines:** Reject any detection above 93% (address region)
2. **Page number reference:** Bottom-right region (90-100%, 80-100% width) should have text
3. **Blackness profile:** Footer region should show spike in blackness (footnotes) after whitespace
4. **Line characteristics:** Footer separator lines are 2-15% of page width

## Expected Performance

Based on analysis of 7 pages with varying content:
- **Whitespace zone detection:** 100% (all pages have identifiable largest zone)
- **Accurate boundary:** 90%+ (footer separator at zone boundary)
- **Address line avoidance:** 100% (by filtering >93% region)

## Advantages Over Previous Approaches

| Issue | Previous | New Strategy |
|-------|----------|--------------|
| Detected address line | Searched 88-95%, found address at 93% | Filter out >93% region explicitly |
| Institutional sign noise | Could confuse whitespace at 40-50% | Start from 50% downward only |
| Variable footer position | Fixed search region 75-95% | Dynamic based on largest whitespace |
| Short line segments missed | Strict line detection only | Use whitespace boundary as primary |
| No content validation | Relied only on isolation checks | Validate with blackness profile |

## Implementation Plan

1. ✅ Analyze complete PDF to identify patterns
2. 🔄 Implement whitespace-zone-based detector
3. ⏳ Test on all 13 PDFs (93 pages)
4. ⏳ Validate against good examples (balanced_footer_test/)
5. ⏳ Integrate into full extraction pipeline
