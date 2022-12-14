# Treball Final de Màster
## Màster en Ciència de Dades- UOC
### Anàlisi dels factors determinants d’incendis forestals i predicció del risc a Catalunya

Aquest conjunt de codis s'ha utilitzat en primer lloc per analitzar les dades històrics dels incendis forestals a Catalunya, veure la seva relació amb variables orogràfiques, meteorològiques, de vegetació i usos del sol.

A continuació s'ha creat un model predictiu del risc a Catalunya per a un determinat dia, utilitzant una xarxa neuronal convolucional.

A més s'han delimitat les àrees cremades, classificat la severitat i quantificat les emissions de CO2 en els 2 grans incenis forestals del 2022.

Els codis s'executen sequencialment:
  * 01: Neteja de les dades històriques d'incendis disponibles a la web del [DAAC.](https://agricultura.gencat.cat/ca/serveis/cartografia-sig/bases-cartografiques/boscos/incendis-forestals/incendis-forestals-format-shp/)
  * 02: Consulta de les dades meteorològiques mitjançant l'[API Climate Data Store](https://cds.climate.copernicus.eu/#!/home) i el conjunt [ERA5 reanalisis.](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-pressure-levels?tab=overview)
  * 03: Estadística inferencial per trobar si les mitjanes de les variables són diferents en els casos d'incendis respecte els casos de no incendis.
  * 04: Importància de variables mitjançant regressió logística.
  * 05: Entrenament de la xarxa neuronal.
  * 06: Generació dels mapes de risc per a 4 dies determinats.
  * 07: Tranformació dels rasters a poligons per poder publicar-los a [CARTO.](https://xpascuet.carto.com/builder/fea2609f-09e0-4afe-a0c6-daf4e3f6c828/embed)
  * 08: Obtenció de les àrres cremades dels 2 grans incendis del 2022 mitjançant l'API del SentinelHub, utilitza les funcions creades a l'script burned_area_utils.py
  * 09: Quantificació de la biomasssa pèrduda i del CO2 emès en els incendis de l'apartat anterior.
  
  
