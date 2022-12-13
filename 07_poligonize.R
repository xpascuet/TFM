library(raster)
library(rgdal)
library(ggplot2)
library(RColorBrewer)

predictions <- c("prediction_02_01_2021.tif", "prediction_20_09_2017.tif", "prediction_08_03_2012.tif", "prediction_15_06_2022.tif")

# Classification matrix
reclass_df <- c(-1, 0.2, 1,
                  0.2, 0.4, 2,
                  0.4, 0.6, 3,
                  0.6, 0.8, 4,
                  0.8, 1, 5)
reclass_m <- matrix(reclass_df,
                      ncol = 3,
                      byrow = TRUE)

for (c in predictions){
  r <- raster(c)
  # Resample raster with a x4 factor
  agg = aggregate(r, 4)
  agg_classified <- reclassify(agg, reclass_m)
  pol <- rasterToPolygons(agg_classified, dissolve=T)
  name <- (strsplit(c,split = '[.]'))
  file_name <- paste(unlist(name)[1],".geojson", sep="")
  writeOGR(pol, file_name, 'risc', driver="GeoJSON")
}

