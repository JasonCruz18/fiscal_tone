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
file_path <- file.path(folder_path, "metas_fiscales.xlsx")

# Read the file
df <- read_excel(file_path)

# Convert 'meta' column to a factor for correct ordering
df$meta <- factor(df$meta, levels = c("Meta cumplida", "Meta incumplida", "Regla suspendida"))

# Check data structure
str(df)


#*******************************************************************************
# Plots
#*******************************************************************************

# Create the plot for fiscal indicators
ggplot(df, aes(x = year, y = y_value, color = meta, fill = meta)) +
  # Plot bubbles with size
  geom_point(aes(size = size), shape = 21, stroke = 1, color = "#292929") +
  scale_size_continuous(range = c(4, 20)) + # Adjust size range for bubbles
  scale_color_manual(values = c("blue", "red", "transparent")) + # Custom colors for categories
  scale_fill_manual(values = c("blue", "red", "transparent")) +
  labs(
    x = NULL, 
    y = "Ejecución - Meta (% del PIB)",
    color = "Estado de la Meta"  # Set the correct legend title for the meta categories
  ) +
  theme_minimal(base_size = 14) + # Clean theme with base size of 14
  theme(
    axis.text = element_text(size = 14),  # Text size for axes
    plot.title = element_text(face = "bold"),  # Title in bold
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),  # Major grid in light gray
    panel.grid.minor = element_line(color = "#f5f5f5", linewidth = 0.65),  # Minor grid in light gray
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),  # Black border for panel
    panel.background = element_blank(),  # Transparent background
    legend.position = c(0.98, 0.98),  # Position legend at the top right
    legend.justification = c("right", "top"), # Adjust legend position
    legend.box = "vertical",  # Vertical box for the legend
    legend.background = element_rect(
      fill = alpha("white", 0.7), # 70% transparency for the legend background
      color = "gray80",  # Light gray border for the legend
      linewidth = 0.3  # Border thickness
    ),
    legend.key = element_blank(),  # Remove color symbols from legend
    legend.title = element_text(size = 14),  # Legend title size
    legend.text = element_text(size = 12)  # Legend text size
  ) +
  geom_text(data = subset(df, year == 2015), aes(label = "*"), vjust = -1, size = 6) + # Add asterisk in 2015
  geom_hline(yintercept = 0, linetype = "solid", color = "black", size = 1) + # Add line at y = 0
  scale_x_continuous(breaks = seq(2000, 2025, 5), labels = c("2000", "2005", "2010", "2015", "2020", "2025 (P)")) + # X-axis ticks adjustment
  guides(
    color = guide_legend(title = "Estado de la Meta", override.aes = list(size = 5)),  # Show only "Meta" legend
    fill = "none",  # Remove redundant `fill` legend
    size = "none"  # Remove `size` legend
  )


