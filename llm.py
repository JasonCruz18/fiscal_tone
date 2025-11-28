# Libraries

import pandas as pd
import matplotlib.pyplot as plt
import openai
import time

from openai import OpenAI
import os

# Inicializar cliente con tu API Key (usando variable de entorno)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Verification

import os
print("OPENAI_API_KEY" in os.environ)

# Loading input

# Asegúrate que tu archivo esté en el mismo directorio
df = pd.read_json("metadata/cf_normalized_paragraphs.json")  # Debe contener una columna 'text' y 'date'

# Inicializar columnas para los resultados
df["fiscal_risk_score"] = None        # Puntaje del 1 al 5
df["risk_index"] = None               # Normalizado a escala 0.0–1.0

# Asegurar columnas necesarias
assert 'text' in df.columns, "Falta columna 'text' con los párrafos"
assert 'date' in df.columns, "Falta columna 'date' con la fecha del documento"

# Convert to data type

import pandas as pd

def convert_date_column(df):
    """
    Convierte la columna 'date' a tipo datetime si existe en el DataFrame.
    
    Argumento:
    - df: pandas.DataFrame
    
    Retorna:
    - df: pandas.DataFrame con la columna 'date' convertida, si corresponde.
    """
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

df = convert_date_column(df)

df["date"].dtype

# Function to get score from GPT 5

context = """
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

def get_llm_score(text):
    prompt = f"""
Eres un analista técnico del Consejo Fiscal de Perú. Evalúa el siguiente párrafo extraído de un informe técnico del Consejo Fiscal (CF), donde se emite una opinión sobre el desempeño fiscal del Ministerio de Economía y Finanzas (MEF) en cuanto al cumplimiento de las metas fiscales.

Tu tarea es asignar un **puntaje del 1 al 5** según el **nivel de preocupación o alerta fiscal expresado en el texto**.

Interpretación:
- 1 = Sin preocupación fiscal (cumplimiento de metas, transparencia fiscal, planificación multianual)
- 2 = Ligera preocupación (riesgo fiscal potencial, desviación del déficit, dependencia de ingresos extraordinarios)
- 3 = Neutral (descripción técnica, gestión dentro del marco, sin juicio valorativo)
- 4 = Alta preocupación (incumplimiento de metas, relajamiento fiscal, incertidumbre macroeconómica)
- 5 = Alarma fiscal (críticas severas, riesgo de sostenibilidad de la deuda, independencia fiscal comprometida)

Devuelve solo un número del 1 al 5.

Texto:
\"\"\"{text}\"\"\"
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=5,
        )
        result = response.choices[0].message.content.strip()
        if result in {'1', '2', '3', '4', '5'}:
            return int(result)
        else:
            print(f"⚠️ Respuesta inesperada: {result}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

#  Run classification with backup (250) and credit control

import openai
print(openai.__version__)

from datetime import datetime

start = time.time()

for i, row in df.iterrows():
    if pd.notna(row["fiscal_risk_score"]):
        continue  # Ya procesado

    score = get_llm_score(row["text"])

    # Guardar score
    df.at[i, "fiscal_risk_score"] = score
    df.at[i, "risk_index"] = score / 5 if score else None

    # Backup cada 250 filas
    if i % 250 == 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        df.to_json(f"backup_fiscal_risk_{timestamp}.json", index=False)
        print(f"💾 Backup guardado en fila {i} - {timestamp}")

    time.sleep(1.2)  # Control para no sobrecargar

end = time.time()
print(f"✅ Proceso completado en {round((end - start)/60, 2)} minutos.")

# Save results

df.to_json("data/output/llm_output.json", index=False)

df.to_csv("data/output/llm_output.csv", index=False)

# Aggregation

df_doc_avg = df.groupby(['title', 'date']).agg(
    avg_risk_score=('fiscal_risk_score', 'mean'),
    avg_risk_index=('risk_index', 'mean'),
    n_paragraphs=('fiscal_risk_score', 'count')
).reset_index()

df_score_dist = (
    df.pivot_table(index=['title', 'date'], 
                   columns='fiscal_risk_score', 
                   values='text', 
                   aggfunc='count', 
                   fill_value=0)
    .reset_index()
    .rename(columns={1: 'score_1', 2: 'score_2', 3: 'score_3', 4: 'score_4', 5: 'score_5'})
)

# Save aggregated scores

# Visualize

df_doc_summary = pd.merge(df_doc_avg, df_score_dist, on=['title', 'date'])

df_doc_summary = df_doc_summary.sort_values("date")

# Calcula la media móvil centrada con ventana de 3 documentos
df_doc_summary["cma_risk_index"] = df_doc_summary["avg_risk_score"].rolling(window=3, center=True).mean()

## stacked areas

print(df_doc_summary['date'].dtype)

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Asegurar que la columna 'date' sea datetime
df_doc_summary['date'] = pd.to_datetime(df_doc_summary['date'], errors='coerce')

# Asegurar orden por fecha
df_doc_summary = df_doc_summary.sort_values("date").reset_index(drop=True)

# Crear columna string para eje X
df_doc_summary['date_str'] = df_doc_summary['date'].dt.strftime('%Y-%m-%d')

# Pesos del suavizamiento
weights = np.array([1, 2, 1])

# Aplicar CMA con bordes extendidos
for col in ['score_1', 'score_2', 'score_3', 'score_4', 'score_5']:
    series = df_doc_summary[col].copy()

    middle_cma = (
        series.rolling(window=3, center=True)
        .apply(lambda x: np.dot(x, weights) / 4, raw=True)
    )

    # Bordes
    first = series.iloc[0]
    second = series.iloc[1]
    first_smoothed = (3 * first + second) / 4

    last = series.iloc[-1]
    penultimate = series.iloc[-2]
    last_smoothed = (3 * last + penultimate) / 4

    # Insertar bordes
    middle_cma.iloc[0] = first_smoothed
    middle_cma.iloc[-1] = last_smoothed

    df_doc_summary[f'{col}_cma'] = middle_cma

# Configuración para el gráfico
cols_cma = ['score_1_cma', 'score_2_cma', 'score_3_cma', 'score_4_cma', 'score_5_cma']
labels = ['1 (bajo)', '2', '3', '4', '5 (alto)']
colors = ['#40312C', '#634C44', '#ff8575', '#ED2939', '#1F305E']

# Crear figura
fig, ax = plt.subplots(figsize=(14, 6))

# Áreas apiladas suavizadas
ax.stackplot(df_doc_summary['date_str'], 
             *[df_doc_summary[col] for col in cols_cma],
             labels=labels,
             colors=colors)

# Etiquetas
ax.set_ylabel("Proporción de Párrafos", fontsize=16)

# Eje X
ax.tick_params(axis='x', labelrotation=90, labelsize=12)

# Eje Y con 2 decimales
ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
ax.tick_params(axis='y', labelsize=12)

# Rejilla estética
ax.grid(True, color='#f5f5f5', alpha=0.3, linewidth=1)

# Leyenda personalizada
legend = ax.legend(loc='upper left', frameon=True)
legend.get_frame().set_facecolor('#f5f5f5')
legend.get_frame().set_alpha(0.5)
legend.get_frame().set_edgecolor('#f5f5f5')  # contorno sin transparencia
legend.get_frame().set_linewidth(2)  # grosor del contorno

# Margen automático
plt.tight_layout()

# Guardar gráfico
plt.savefig("Fig_Distribucion.png", dpi=300)
plt.show()

## Fiscal Tone Index

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Calcular índice de tono fiscal
df_doc_summary["fiscal_tone_index"] = (3 - df_doc_summary["avg_risk_score"]) / 2

# Suavizamiento CMA (1-2-1)
weights = np.array([1, 2, 1])
series = df_doc_summary["fiscal_tone_index"].copy()

cma = series.rolling(window=3, center=True).apply(lambda x: np.dot(x, weights) / 4, raw=True)
cma.iloc[0] = (3 * series.iloc[0] + series.iloc[1]) / 4
cma.iloc[-1] = (3 * series.iloc[-1] + series.iloc[-2]) / 4

df_doc_summary["fiscal_tone_index_cma"] = cma

# Graficar
fig, ax = plt.subplots(figsize=(14, 6))

# Serie original (transparente)
ax.plot(df_doc_summary["date_str"], df_doc_summary["fiscal_tone_index"],
        label="Tono Fiscal", linestyle='--',
        marker='o', alpha=0.25, color="#634C44")

# Serie suavizada (principal)
ax.plot(df_doc_summary["date_str"], df_doc_summary["fiscal_tone_index_cma"],
        label="Tono Fiscal (Promedio Móvil)", linewidth=2, color="#40312C")

# Línea horizontal en 0 (tono neutral)
ax.axhline(0, color='#292929', linestyle='-', linewidth=1)

# Eje Y
ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
ax.tick_params(axis='y', labelsize=12)

# Eje X
ax.tick_params(axis='x', labelrotation=90, labelsize=12)

# Rejilla solo cada 2 fechas
x_ticks = np.arange(len(df_doc_summary["date_str"]))
ax.set_xticks(x_ticks)  # etiquetas en todas las fechas
ax.grid(False)  # desactivar rejilla por defecto

# Dibujar palos verticales cada 2 ticks
for i in range(0, len(x_ticks), 2):
    ax.axvline(x=i, color='#f5f5f5', linewidth=1, zorder=0)

# Etiqueta eje Y
ax.set_ylabel("Índice de Tono Fiscal", fontsize=16)

# Leyenda personalizada
legend = ax.legend(loc='upper right', frameon=True)
legend.get_frame().set_facecolor('white')
legend.get_frame().set_alpha(0.5)
legend.get_frame().set_edgecolor('#f5f5f5')
legend.get_frame().set_linewidth(2.5)

# Ajuste final
plt.tight_layout()

# Guardar y mostrar
plt.savefig("Fig_Tono.png", dpi=300)
plt.show()


