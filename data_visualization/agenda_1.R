#*******************************************************************************
# Plotting Charts for Fiscal indicators    
#*******************************************************************************

#-------------------------------------------------------------------------------
# Author: Jason Cruz
#...............................................................................
# Program: fiscal_indicators.R
# + First Created: 09/10/25
# + Last Updated: 09/10/25
#-------------------------------------------------------------------------------



#*******************************************************************************
# Load and Install Required Libraries
#*******************************************************************************

# Vector of required packages
required_packages <- c(
  "readxl", "ggplot2", "dplyr", "lubridate", "forcats", 
  "scales", "patchwork", "ggrepel", "tidyr", "tidyverse"
)

# Install any packages that are not already installed
installed <- required_packages %in% rownames(installed.packages())
if (any(!installed)) {
  install.packages(required_packages[!installed])
}

# Load all required libraries
invisible(lapply(required_packages, library, character.only = TRUE))



#*******************************************************************************
# Load and Prepare the Dataset
#*******************************************************************************

# Prompt user to choose a folder
folder_path <- rstudioapi::selectDirectory(
  caption = "Select the folder containing the Excel file",
  path = getwd()
)

# Construct file path
file_path <- file.path(folder_path, "fiscal_indicators.xlsx")

# Read the file
df <- read_excel(file_path)

# Ensure proper column names: Year, pub_balance, pub_debt
df <- df %>%
  rename(
    year = 1,
    pub_balance = 2,
    pub_debt = 3
  )



#*******************************************************************************
# Plots
#*******************************************************************************

#*******************************************************************************
# Chart 1: Public Balance (bars, left axis) & Public Debt (line, right axis)
#*******************************************************************************

# Split data into historical (<=2024) and projection (>=2025)
df_hist <- df %>% filter(year <= 2024)
df_proj <- df %>% filter(year >= 2025)

# Primary axis range
y1_min <- -8
y1_max <- 6
y1_breaks <- seq(y1_min, y1_max, by = 2)

# Secondary axis range
y2_min <- 15
y2_max <- 55
y2_breaks <- seq(y2_min, y2_max, by = 5)

# Transformation between axes
scale_factor <- (y1_max - y1_min) / (y2_max - y2_min)
intercept <- y1_min - scale_factor * y2_min

# Build plot
fiscal_plot <- ggplot() +
  # Bars for pub_balance (historical)
  geom_col(
    data = df_hist,
    aes(x = year, y = pub_balance,
        fill = "Balance del Sector Público (% del PBI) - Histórico"),
    color = "black"
  ) +
  # Bars for pub_balance (projection, 50% transparency)
  geom_col(
    data = df_proj,
    aes(x = year, y = pub_balance,
        fill = "Balance del Sector Público (% del PBI) - Proyección"),
    color = "black",
    alpha = 0.75
  ) +
  
  # Línea horizontal en cero
  geom_hline(yintercept = 0, color = "black", linewidth = 1) +
  
  # Line for pub_debt (historical)
  geom_line(
    data = df_hist,
    aes(x = year,
        y = pub_debt * scale_factor + intercept,
        color = "Deuda Pública (% del PBI) - Histórico"),
    size = 1.5
  ) +
  # Points for pub_debt (historical)
  geom_point(
    data = df_hist,
    aes(x = year,
        y = pub_debt * scale_factor + intercept,
        color = "Deuda Pública (% del PBI) - Histórico"),
    size = 2.75
  ) +
  # Points for pub_debt (projection)
  geom_point(
    data = df_proj,
    aes(x = year,
        y = pub_debt * scale_factor + intercept,
        color = "Deuda Pública (% del PBI) - Proyección"),
    size = 2.75
  ) +
  
  # Axes
  scale_y_continuous(
    name = "Balance del Sector Público (% del PBI)",
    limits = c(y1_min, y1_max),
    breaks = y1_breaks,
    expand = expansion(mult = c(0, 0.02)),
    sec.axis = sec_axis(
      ~ (. - intercept) / scale_factor,
      name = "Deuda Pública (% del PBI)",
      breaks = y2_breaks
    )
  ) +
  scale_x_continuous(breaks = seq(min(df$year), max(df$year), by = 2)) +
  
  # Manual colors
  scale_fill_manual(values = c(
    "Balance del Sector Público (% del PBI) - Histórico" = "#005f5e",
    "Balance del Sector Público (% del PBI) - Proyección" = "#005f5e"
  )) +
  scale_color_manual(values = c(
    "Deuda Pública (% del PBI) - Histórico" = "#00DFA2",
    "Deuda Pública (% del PBI) - Proyección" = "#00DFA2"
  )) +
  
  # Labels
  labs(x = NULL, fill = NULL, color = NULL) +
  
  # Theme
  theme_minimal(base_size = 14) +
  theme(
    axis.text = element_text(size = 14),
    plot.title = element_text(face = "bold"),
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.grid.minor = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),
    
    # Put both legends inside chart (top-right corner)
    legend.position = c(0.98, 0.98),
    legend.justification = c("right", "top"),
    legend.box = "vertical",
    legend.background = element_rect(
      fill = alpha("white", 0.7),
      color = "gray80",
      linewidth = 0.3
    )
  ) +
  
  # Guides (so fill & color legends are both shown)
  guides(
    fill = guide_legend(title = NULL),
    color = guide_legend(title = NULL)
  )

# Display
print(fiscal_plot)

ggsave(
  filename = file.path(folder_path, "fiscal_indicators.png"),
  plot = fiscal_plot,
  width = 12, height = 6, dpi = 300, bg = "white"
)

