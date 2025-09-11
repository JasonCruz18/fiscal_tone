#*******************************************************************************
# Plotting Charts for Tenure Length of Peru's Economy and Finance Ministers    
#*******************************************************************************

#-------------------------------------------------------------------------------
# Author: Jason Cruz
#...............................................................................
# Program: ministers_tenure.R
# + First Created: 07/18/25
# + Last Updated: 07/19/25
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
file_path <- file.path(folder_path, "mef_ministers_dataset.xlsx")

# Read the file
df <- read_excel(file_path)



#*******************************************************************************
# Plots
#*******************************************************************************


#-------------------------------------------------------------------------------
# Chart 1: Timeline of Economy and Finance Ministers' Tenure
#-------------------------------------------------------------------------------

# STEP 1: Compute the number of days in office and order ministers by start date
df <- df %>%
  mutate(
    duration_days = as.numeric(difftime(end_date, start_date, units = "days")),
    minister_name = fct_reorder(minister_name, start_date)
  )

# STEP 2: Plot the tenure timeline using colored bars
ministers_tenure_plot <- ggplot(
  df,
  aes(x = start_date, xend = end_date, y = minister_name, yend = minister_name)
) +
  geom_segment(aes(color = duration_days), linewidth = 5) +
  scale_color_gradientn(
    colours = c("#033280", "#00DFA2", "#FFF183", "#ff8575", "#E6004C"),
    values = rescale(c(1000, 700, 400, 200, 0)),
    name = "Días en la oficina"
  ) +
  scale_x_datetime(date_labels = "%Y", date_breaks = "2 years") +
  labs(
    x = "",
    y = "Ministro"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text.y = element_text(size = 14),
    axis.text.x = element_text(size = 14),
    plot.title = element_text(face = "bold"),
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.grid.minor = element_blank(),  # <-- se quitó la rejilla secundaria
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),
    legend.position = c(0.98, 0.02),
    legend.justification = c("right", "bottom"),
    legend.background = element_rect(
      fill = alpha("white", 0.5),  # 50% transparency
      color = "#F5F5F5",
      linewidth = 0.75
    )
  )


# STEP 3: Display and export the Gantt-like chart
print(ministers_tenure_plot)

ggsave(
  filename = file.path(folder_path, "Fig_Ministros1.png"),
  plot = ministers_tenure_plot,
  width = 12,
  height = 6,
  dpi = 300,
  bg = "white"
)


#-------------------------------------------------------------------------------
# Chart 2: Distribution of Ministers' Tenure by President
#-------------------------------------------------------------------------------

# STEP 1: Create custom president labels including start and end year
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
  arrange(desc(latest_start))  # Most recent first

# STEP 2: Merge labels into original dataset
df <- df %>%
  left_join(president_labels %>% select(president, president_label), by = "president")

# STEP 3: Order factor levels for legend display
levels <- president_labels$president_label
if (any(df$president_label == "")) {
  levels <- c(levels, "")
}
df$president_label <- factor(df$president_label, levels = levels)

# STEP 4: Define a consistent color palette based on the number of presidents
custom_colors <- rev(c(
  "#033280", "#033280",  # Greens (recent)
  "#00DFA2", "#00DFA2",  # Dark greens
  "#FFF183", "#FFF183",  # Yellows
  "#ff8575", "#ff8575",  # Pinks
  "#E6004C", "#E6004C"   # Reds (older)
))[seq_along(levels)]  # Match number of levels

# STEP 5: Build histogram of tenure distribution by president
tenure_distribution <- ggplot(df, aes(x = duration_days, fill = president_label)) +
  geom_histogram(
    binwidth = 100,
    color = "black",
    linewidth = 0.3,
    alpha = 0.90,
    position = "stack"
  ) +
  scale_fill_manual(values = custom_colors) +
  scale_x_continuous(
    breaks = seq(0, max(df$duration_days, na.rm = TRUE), by = 100),
    expand = expansion(mult = c(0, 0.02))
  ) +
  scale_y_continuous(
    labels = scales::number_format(accuracy = 0.01)  # <-- dos decimales en eje Y
  ) +
  labs(
    x = "Días en la oficina",
    y = "Número de ministros",
    fill = "Presidente"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text = element_text(size = 14),
    plot.title = element_text(face = "bold"),
    panel.grid.major = element_line(color = "#f5f5f5", linewidth = 0.65),
    panel.grid.minor = element_blank(),  # <-- se elimina la grilla secundaria
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.5),
    legend.position = c(0.98, 0.98),
    legend.justification = c("right", "top"),
    legend.background = element_rect(
      fill = alpha("white", 0.5),
      color = "#f5f5f5",
      linewidth = 0.75
    )
  )



# STEP 6: Display and export the histogram plot
print(tenure_distribution)

ggsave(
  filename = file.path(folder_path, "Fig_Ministros2.png"),
  plot = tenure_distribution,
  width = 12,
  height = 6,
  dpi = 300,
  bg = "white"
)

