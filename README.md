# RWQForecast

**RWQForecast (Remote Water Quality Forecast)** is a web application designed for short-term forecasts of water quality changes in reservoirs over a timeframe of days, for analyzing temporal changes in water quality within reservoirs, and for assessing the spatial distribution of water quality within a reservoir for a given date. The analysis is based on combination of the **Sentinel 2** satellite data and their analysis using **AI Machine Learning and Deep Learning** methods.

RWQForecast offers the following options for processing and evaluating satellite data:

    
- Estimation of water quality in reservoirs
- Evaluation of temporal changes
- Short-term forecast of water quality changes
- Assessment of spatial distribution of water quality in reservoirs
    
RWQForecast allows evaluation of the following parameters:
    
- ChlA – Chlorophyll-a concentration (µg.l⁻¹)
    
Upcoming models will include:
    
- ChlB – Chlorophyll-b concentration (µg.l⁻¹)
- TSS – Total suspended solids (mg.l⁻¹)
- PC – Phycocyanin concentration (µg.l⁻¹)
- APC – Allophycocyanin concentration (µg.l⁻¹)
- PE – Phycoerythrin concentration (µg.l⁻¹)
- CX – Carotenoids and xanthophylls concentration (µg.l⁻¹)
- SD – Secchi disk transparency (m)

The system's functionality is designed to minimize user input requirements. The web application handles the user interface, where users simply select a reservoir from a map or list and specify the desired water quality parameters.

The source code is available at: https://github.com/JakubBrom/RWQForecast. The system is written in Python, the web service uses the Flask microframework, and the database is PostgreSQL/PostGIS.


## Status

**Testing version.**

The testing web page is available at http://160.217.162.143:8080/ (can be unavailable because the development). The later version will be placed at https://rwqforecast.com $${\color{red}(upcoming)}$$.

$${\color{red}Testing data available for Orlík, Velký Tisý, Římovská přehrada and Encoro de Belesar}$$.

## Authors and Collaborators

Jakub Brom - libretto, drama, roles, actors, stage, light design, prompter, masks, coffeelings and other issues

Václav Nedbal - data acquisition, water field sampling, spectral measurement, laboratory preparation of samples 

Blanka Tesařová - laboratory analyses

Jan Kuntzman - field work, laboratory preparation of samples

## License

GNU GPL v. 3 or later

© 2024 Jakub Brom, University of South Bohemia in České Budějovice, Faculty of Agriculture and Technology

© 2024 AIHABs Consorcium

E-mail: jbrom@fzt.jcu.cz


## Citation and References

BROM, Jakub, Václav NEDBAL, Blanka TESAŘOVÁ a Jan KUNTZMAN, 2024. RWQForecast: System for assessment and prediction of water quality in reservoirs from satellite data. Software. České Budějovice: University of South Bohemia in České Budějovice.

```bibtex:
@misc{brom_rwqforecast_2024,
    address = {České Budějovice},
    title = {{RWQForecast}: {System} for assessment and prediction of water quality in reservoirs from satellite data. Software.},
    url = {https://github.com/JakubBrom/RWQForecast},
    publisher = {University of South Bohemia in České Budějovice},
    author = {Brom, Jakub and Nedbal, Václav and Tesařová, Blanka and Kuntzman, Jan},
    year = {2024},
}
```


## Acknowledgement

<p>The RWQForecast system was funded by the <b>ERA-NET AquaticPollutants Joint Transnational Call (GA N◦ 869178 AI-powered Forecast for Harmful Algae Bloom (AIHABs))</b>. This ERA-NET is an integral part of the activities developed by the Water, Oceans, and AMR Joint Programming Initiatives.</p>
<p>The RWQForecast was suported by projet of the Technological Agency of the Czech Republic TH76030001 <b>"Předpověď vývoje škodlivého vodního květu pomocí umělé inteligence"</b></p>
<p>The RWQForecast system was developed as part of the <b>AIHABs consortium</b>, in collaboration with the following partners:
    <ul>
        <li>Technical University Dublin, Ireland - Dr. Ahmend Elsidig Nasr (Head of the project)</li>
        <li>University of South Bohemia in České Budějovice, Czech Republic (Dr. Jakub Brom)</li>            
        <li>Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences, Germany (Dr. Mohammedmehdi Saberioon)</li>
        <li>Universidad Santiago de Compostela, Spain (prof. Fernando Cobo)</li>
        <li>Universidad Autónoma de Madrid, Spain (prof. Antonio Quesada del Coral)</li>
        <li>Norwegian University of Science and Technology, Norway (Dr. Marcos Xosé Álvarez-Cid)</li>
        <li>International Iberian Nanotechnology Laboratory - INL, Portugal (Dr. Begoña Espiña)</li>
    </ul>
</p>
<p>The RWQForecast system was supported by the following partners:
    <ul>
        <li>Povodí Vltavy, State Enterprise, Czech Republic</li>
        <li>Povodí Labe, State Enterprise, Czech Republic</li>
        <li>Povodí Ohře, State Enterprise, Czech Republic</li>
    </ul> 
</p>
    
<p>Our thanks belongs to our colleagues for their help.</p>


# RWQForecast documentation

The RWQForecast service has two parts. The first is a user interface (frontend) and the second is computational which provide data downloading and processing. The computational unit provides the data/results to the user with using the database, which is connected with the user interface. $${\color{red}The computational unit is implemented in the RWQForecast services, however it is not linked with the frontend yet}$$.
## User interface

The RWQForecast system is designed to be user-friendly and intuitive. Some parts are still under development. The following tutorial provides a step-by-step guide to using the system:
    
### 1. User account
        
- The user registers using the "Sign Up" tab.
- After successful registration, the user receives an email with a confirmation link.
- After confirming the email, the user can log in to the system.
- The user logs in to their OpenEO user account to obtain a token to perform analyses. If the user does not have an OpenEO account, they must register $${\color{red}(upcoming)}$$.
        
### 2. Logging in
            
- The user logs in to the system using the "Login" tab.
- After successful login, the user is redirected to the "Home" tab.
        
### 3. Analysis
            
From the reservoir selection form or the map window, the user selects the desired reservoir, the evaluation parameter, and the prediction model.
After confirming the selection, the time series for the chosen parameter and reservoir is displayed for all available data.
Missing data in the time series can be filled in using the "Update dataset" button, which starts the process of downloading data and feature calculation.

A table displays information about the reservoir and the dataset after confirmation.
The time series line chart presents the average, median, and confidence intervals.
The forecast chart shows a two-week prediction as an interactive line graph $${\color{red}(upcoming)}$$.
Time series and forecast data can be downloaded as a value table $${\color{red}(upcoming)}$$.
            
The user can display the spatial distribution of values for the selected reservoir. After selection of the particular date of the data acquisition and confirmation, a table with statistics for the reservoir and selected date is generated $${\color{red}(upcoming)}$$ and an interactive graph visualizing the spatial distribution of values across the reservoir is displayed.

Data in the form of a point vector layer can be downloaded by clicking the "Download data" button $${\color{red}(upcoming)}$$.

Statistical indicators are computed from interpolated data using the inverse distance weighting (IDW) interpolation method $${\color{red}(upcoming)}$$.

For adding a new water reservoir, user can click the "Add new reservoir" button which goes to the "Select reservoir" window. The page provides selection of the reservoir from the map for data processing. After confirming the selection the system requests confirmation again and then initiates the analysis.

Once the analysis starts, the system notifies the user in a new application window.

After the analysis is completed, the user receives an email notification with a link to the results.

## Computation workflow

The computation unit (RWQForecas-engine) is a software which provides all the processing steps of the data including satellite data downloading, feature calculation/prediction and forecast of the water quality parameters. The RWQForecast engine is available at https://github.com/JakubBrom/RWQForecast-engine. 

### 1. Downloading the vector layer for the selected reservoir
    
The user selects a reservoir in the application, which is retrieved from the OpenStreetMap database and stored in the system's database. Users can select any reservoir worldwide, with processing available for reservoirs larger than 1 hectare.
    
### 2. Defining points within the reservoir
    
The system generates spatial points inside the selected reservoir using OpenStreetMap as a reference. Each point serves as a spatial reference for processing time series data, allowing interpolation to reconstruct the spatial distribution of values for a given time interval. The approach considers the geometric complexity of reservoirs, ensuring that areas such as bays are included in the analysis. The point density is set to 100 points per km², with adjustments for small and large reservoirs. The system randomly selects and processes a maximum of 5,000 points per reservoir to optimise computational efficiency.
    
### 3. Data retrieval
    
The system automatically downloads data for the defined points from Sentinel-2 satellite imagery available in the ESA OpenEO archive. Meteorological data for each location is retrieved from OpenMeteo.
    
### 4. Calculation of water quality parameters
    
In this step, a pre-trained AI estimation model is used to compute the requested water quality parameters based on the corresponding data stored in the database.
    
### 5. Imputation of missing values
    
Satellite image data availability is irregular due to weather conditions, especially cloud cover, which varies geographically. The system handles missing data using the Support Vector Machine (SVM) method, which reconstructs a complete daily time series by utilizing the characteristics of each time series along with meteorological data as a coregressor. 
    
### 6. Forecasting
    
The model estimates the probable evolution of time series using historical data and meteorological information as coregressors. The Long Short-Term Memory (LSTM) method is used for prediction, generating forecasts for all selected points within the reservoir. $${\color{red}(upcoming)}$$
    
### 7. Visualization of results and statistical analysis
    
Spatial distribution of data for a given date is visualized using contour plots (ContourPlot).

The web application provides visualization of results using the Plotly library. 

Time series are represented by interactive line charts displaying the mean value, median, and confidence intervals.

Missing data are handled using the connectgaps method, and smoothing is applied for improved clarity.

Statistical indicators are computed from interpolated data using the inverse distance weighting (IDW) interpolation method.
    
    
### 8. User data export $${\color{red}(upcoming)}$$

The application allows users to download time series data for a selected reservoir as a data table, as well as spatial data for individual dates in the form of a point vector layer in the WGS84 coordinate system.


## System limitations

The system has following limitations:
    
- Processing is available for reservoirs larger than 1 hectare.
- Processing is limited to a maximum of 5,000 points per reservoir.
- Processing is limited to a maximum of 16 days for forecasting.
- Processing is limited to a maximum of 10 years for historical data. The data for Sentinel 2 are available from June 2015.
- Water quality prediction accuracy is limited by the quality of Satellite data - The L2A Sen2Cor product is used for the data analysis.
- The number of analyses is limitted by the OpenEO data availability limits for the user.
- The time for analysis can be very long because the OpenEO limis.
    