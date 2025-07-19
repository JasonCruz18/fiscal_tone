# Cargar librerías necesarias
library(readxl)     # Para leer archivos Excel
library(ggplot2)    # Para graficar
library(dplyr)      # Para manipulación de datos
library(lubridate)  # Para manejar fechas
library(forcats)    # Para ordenar factores (eje Y)
library(scales)
library(patchwork)
library(ggrepel)
library(tidyr)
library(tidyverse)

# Leer el archivo Excel (ajusta el nombre si es necesario)
# Asegúrate que el archivo está en tu directorio de trabajo
df <- read_excel("C:/Users/Jason Cruz/OneDrive/Escritorio/mef_ministers_dataset.xlsx")


#-------------------------------------------------------------------------------
# 1
#-------------------------------------------------------------------------------


# Compute duration
df <- df %>%
  mutate(
    duration_days = as.numeric(difftime(end_date, start_date, units = "days")),
    minister_name = fct_reorder(minister_name, start_date)
  )

# Create the plot
ministers_tenure_plot <- ggplot(df, aes(x = start_date, xend = end_date, y = minister_name, yend = minister_name)) +
  geom_segment(aes(color = duration_days), linewidth = 5) +
  scale_color_gradientn(
    colours = c("#005f5e", "#00DFA2", "#FFF183", "#ff8575", "#E6004C"),
    values = rescale(c(1000, 700, 400, 200, 0)),
    name = "Days in Office"
  ) +
  scale_x_datetime(date_labels = "%Y", date_breaks = "2 year") +
  labs(
    title = "Tenure of Peru's Economy and Finance Ministers",
    x = "",
    y = "Minister"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text.y = element_text(size = 14),
    axis.text.x = element_text(size = 14),
    plot.title = element_text(face = "bold"),
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.grid.minor = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),
    legend.position = c(0.98, 0.02),
    legend.justification = c("right", "bottom"),
    legend.background = element_rect(
      fill = alpha("#f5f5f5", 0.5),  # 50% transparency
      color = "#f5f5f5",
      linewidth = 0.75
    )
  )

# Save as PNG with white background
ggsave("C:/Users/Jason Cruz/OneDrive/Escritorio/ministers_tenure.png",
       plot = ministers_tenure_plot,
       width = 12,
       height = 6,
       dpi = 300,
       bg = "white")



#-------------------------------------------------------------------------------
# 2
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# 3
#-------------------------------------------------------------------------------

# Paso 1: Calcular etiquetas personalizadas con años
president_labels <- df %>%
  group_by(president) %>%
  summarize(
    start_year = format(min(start_date), "%Y"),
    end_year = format(max(end_date), "%Y"),
    latest_start = max(start_date),
    .groups = "drop"
  ) %>%
  mutate(
    president_label = paste0(president, " (", start_year, "–", end_year, ")")
  ) %>%
  arrange(desc(latest_start))  # más recientes primero

# Paso 2: Fusionar etiquetas al dataframe original
df <- df %>%
  left_join(president_labels %>% select(president, president_label), by = "president")

# Paso 4: Crear factor ordenado para la leyenda
niveles <- president_labels$president_label
if (any(df$president_label == "")) {
  niveles <- c(niveles, "")
}
df$president_label <- factor(df$president_label, levels = niveles)

# Paso 5: Definir 10 colores coherentes
custom_colors <- rev(c(
  "#66EFC4", "#00DFA2",  # Verdes (más nuevos)
  "#007e7d", "#005f5e",  # Verdes oscuros
  "#FFECA8", "#FFF183",  # Amarillos
  "#FFAAA0", "#ff8575",  # Rosados
  "#FF4C7F", "#E6004C"   # Rojos (más antiguos)
))[seq_along(niveles)]  # Asegurar que solo use los necesarios

# Crear el gráfico
# Crear el gráfico
tenure_distribution <- ggplot(df, aes(x = duration_days, fill = president_label)) +
  geom_histogram(binwidth = 100, color = "black", linewidth = 0.3, alpha = 0.90, position = "stack") +
  scale_fill_manual(values = custom_colors) +
  scale_x_continuous(
    breaks = seq(0, max(df$duration_days, na.rm = TRUE), by = 100),
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(
    title = "Distribución de duración del cargo de Ministros de Economía y Finanzas",
    x = "Duración en días",
    y = "Número de ministros",
    fill = "Presidente"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text = element_text(size = 14),
    plot.title = element_text(face = "bold"),
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.grid.minor = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),
    legend.position = c(0.98, 0.98),  # esquina superior derecha interna
    legend.justification = c("right", "top"),
    legend.background = element_rect(
      fill = alpha("#f5f5f5", 0.5),
      color = "#f5f5f5",
      linewidth = 0.75
    )
  )

print(tenure_distribution)

# Guardar como PNG
ggsave("C:/Users/Jason Cruz/OneDrive/Escritorio/tenure_distribution_by_president.png",
       plot = tenure_distribution,
       width = 12,
       height = 6,
       dpi = 300,
       bg = "white")


