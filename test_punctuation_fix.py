"""
Test punctuation spacing fix
"""
import sys
import json

# Clear module cache
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

import builtins
builtins.input = lambda *args: "."

from data_curation import _normalize_whitespace

# Test the specific example from user
test_text = """Como se mencionó en el informe N 004-2019-CF , las medidas orientadas a disminuir el incumplimiento tributario son relevantes y de carácter prioritario; sin embargo, en la última década se han registrado episodios de reducción del incumplimiento tributario que no representaron un incremento de ingresos permanentes . Contrario al supuesto asumido en el MMM, el CF nota que la tasa de incumplimiento del IGV se incrementó durante el 2019 y advierte que la crisis actual podría llevar a un incremento considerable de este indicador. Al respecto, el CF recomienda recordar que el aumento del incumplimiento tributario durante la crisis del 2009 generó una pérdida de ingresos estimada en 1,1 por ciento del PBI ."""

print("=" * 80)
print("TESTING PUNCTUATION SPACING FIX")
print("=" * 80)
print()

print("BEFORE:")
print("-" * 80)
print(test_text)
print()

cleaned = _normalize_whitespace(test_text)

print("AFTER:")
print("-" * 80)
print(cleaned)
print()

# Count issues
before_spaces = test_text.count(' ,') + test_text.count(' .') + test_text.count(' ;')
after_spaces = cleaned.count(' ,') + cleaned.count(' .') + cleaned.count(' ;')

print("=" * 80)
print(f"Spaces before punctuation: BEFORE={before_spaces}, AFTER={after_spaces}")
print("=" * 80)

if after_spaces == 0:
    print("✓ FIX SUCCESSFUL - All spaces before punctuation removed!")
else:
    print(f"✗ Still {after_spaces} spaces before punctuation remaining")
