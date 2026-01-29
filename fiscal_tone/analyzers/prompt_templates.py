"""
Prompt Templates for LLM Classification.

This module contains the domain context and prompt templates used for
fiscal tone classification with GPT-4o.

The prompts are designed for the Peruvian Fiscal Council (Consejo Fiscal)
opinion documents and include domain-specific context about fiscal policy
deterioration patterns observed since 2016.

Attributes:
    FISCAL_DOMAIN_CONTEXT: Background context on Peruvian fiscal policy
    CLASSIFICATION_PROMPT_TEMPLATE: Template for fiscal risk classification

Example:
    >>> from fiscal_tone.analyzers.prompt_templates import build_classification_prompt
    >>> prompt = build_classification_prompt("El CF considera que...")
"""

# Domain context for classification
# This context helps GPT-4o understand the background of Peruvian fiscal policy
FISCAL_DOMAIN_CONTEXT = """
Sabemos que desde aproximadamente 2016 el manejo de las finanzas públicas ha mostrado signos crecientes de deterioro.
La pérdida de disciplina fiscal, la falta de transparencia y el relajamiento de las reglas fiscales han sido temas
recurrentes en las opiniones del Consejo Fiscal. A ello se suma el impacto de la inestabilidad política —con frecuentes cambios
ministeriales— sobre la capacidad institucional para llevar una política fiscal prudente y sostenible. En este contexto,
el Consejo Fiscal ha venido alertando con más frecuencia y firmeza sobre el incumplimiento de metas fiscales, el deterioro del
balance público, y los riesgos de un endeudamiento creciente y potencialmente insostenible.

Criterios comunes en los informes y comunicados del Consejo Fiscal (según categoría):

1. Cumplimiento y disciplina fiscal:
(disciplina fiscal, incumplimiento de metas fiscales, relajamiento de reglas fiscales, uso inadecuado del gasto público, desviación del déficit fiscal, deterioro del marco fiscal, flexibilización sin justificación, política fiscal procíclica)

2. Riesgo y sostenibilidad:
(riesgo fiscal, riesgo de sostenibilidad de la deuda, endeudamiento excesivo, dependencia de ingresos extraordinarios, vulnerabilidad fiscal estructural, uso de medidas transitorias o no permanentes, incertidumbre macrofiscal)

3. Gobernanza e institucionalidad:
(transparencia fiscal, calidad del gasto público, incertidumbre institucional, falta de planificación multianual, cambios frecuentes en autoridades económicas, debilitamiento institucional, independencia fiscal comprometida, ausencia de reforma estructural)
"""

# Classification instruction template
CLASSIFICATION_INSTRUCTION = """
Clasifica el siguiente párrafo según su grado de preocupación o alerta fiscal. Usa SOLO un número del 1 al 5:

1 = Sin preocupación fiscal (consolidación, cumplimiento, transparencia)
2 = Leve preocupación (riesgos potenciales, dependencia de ingresos extraordinarios)
3 = Neutral o técnico (descripción sin juicio de valor)
4 = Alta preocupación (incumplimiento, relajamiento fiscal, incertidumbre)
5 = Alarma fiscal (crítica severa, riesgo de sostenibilidad de deuda)

Párrafo:
\"\"\"{text}\"\"\"

Responde SOLO con un número (1, 2, 3, 4 o 5):"""

# Score descriptions for documentation and analysis
SCORE_DESCRIPTIONS = {
    1: "Sin preocupación fiscal (consolidación, cumplimiento, transparencia)",
    2: "Leve preocupación (riesgos potenciales, dependencia de ingresos extraordinarios)",
    3: "Neutral o técnico (descripción sin juicio de valor)",
    4: "Alta preocupación (incumplimiento, relajamiento fiscal, incertidumbre)",
    5: "Alarma fiscal (crítica severa, riesgo de sostenibilidad de deuda)",
}


def build_classification_prompt(text: str, include_context: bool = True) -> str:
    """
    Build the full classification prompt for a paragraph.

    Args:
        text: The paragraph text to classify.
        include_context: Whether to include domain context (recommended).

    Returns:
        Complete prompt string ready for GPT-4o.

    Example:
        >>> prompt = build_classification_prompt("El CF considera que...")
        >>> len(prompt) > 100
        True
    """
    if include_context:
        return FISCAL_DOMAIN_CONTEXT + "\n" + CLASSIFICATION_INSTRUCTION.format(text=text)
    else:
        return CLASSIFICATION_INSTRUCTION.format(text=text)


def calculate_fiscal_tone_index(risk_score: float) -> float:
    """
    Calculate the Fiscal Tone Index from a risk score.

    The Fiscal Tone Index transforms the 1-5 risk score into a -1 to +1 scale:
    - +1.0: Maximum fiscal consolidation (score = 1)
    -  0.0: Neutral (score = 3)
    - -1.0: Maximum fiscal alarm (score = 5)

    Formula: (3 - risk_score) / 2

    Args:
        risk_score: Average fiscal risk score (1-5 scale).

    Returns:
        Fiscal Tone Index (-1 to +1 scale).

    Example:
        >>> calculate_fiscal_tone_index(1.0)
        1.0
        >>> calculate_fiscal_tone_index(3.0)
        0.0
        >>> calculate_fiscal_tone_index(5.0)
        -1.0
    """
    return (3 - risk_score) / 2
