# Cargar librerías necesarias
library(readxl)     # Para leer archivos Excel
library(ggplot2)    # Para graficar
library(dplyr)      # Para manipulación de datos
library(lubridate)  # Para manejar fechas
library(forcats)    # Para ordenar factores (eje Y)
library(scales)

# Leer el archivo Excel (ajusta el nombre si es necesario)
# Asegúrate que el archivo está en tu directorio de trabajo
df <- read_excel("C:/Users/Jason Cruz/OneDrive/Escritorio/mef_ministers_dataset.xlsx")

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
