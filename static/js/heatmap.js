// Načtení dat pro interpolaci a vytvoření heatmapy
function plotSpatialWR(dataUrl, divId){
    $(document).ready(function() {
        $('#interp-btn').click(function() {
            const osm_id = $('#sel_wr_sp').val();
            const feature = $('#select_wq_sp').val();
            const date = $('#datepicker').val();
            const model_id = $('#sel_model_sp').val();

            $('#spinner').show();
            $('#sp_results').show();
            document.getElementById('sp_results').scrollIntoView({ behavior: 'smooth' });
            $('#controls').show();
            $('#downl-vect-text').show();
            $('#downl-vect').show();

            $.ajax({
                url: dataUrl,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, date: date, model_id: model_id }),
                success: function(response) {
                    const x = response.x;
                    const y = response.y;
                    const z = response.z;
                    const m = response.m;

                    const customColorscale = [
                        [0, 'rgb(0, 12, 140)'],
                        [0.5, 'rgb(228, 245, 104)'],
                        [1, 'rgb(7, 125, 25)']
                    ];

                    const maskColorScale = [
                        [0, 'white'],
                        [1, 'white']
                    ];

                    originalZmin = Math.min(...z.flat());
                    originalZmax = Math.max(...z.flat());

                    const mapData = {
                        z: z,
                        x: x,
                        y: y,
                        connectgaps: true,
                        type: 'contour',
                        line: {
                            smoothing: 0.85,
                            color: 'rgb(150,150,150)'
                        },
                        colorscale: customColorscale,
                        zmin: originalZmin,
                        zmax: originalZmax,
                        name: 'Data',
                        hovertemplate: '%{z:.2f}<extra></extra>',
                        colorbar: {
                            title: {
                                text: 'Concentration',
                                side: 'bottom'
                            },
                            orientation: 'h',
                            x: 0.5,
                            xanchor: 'center',
                            y: -0.3,
                            len: 0.5,
                            thickness: 15
                        }
                    };

                    const maskData = {
                        z: m,
                        x: x,
                        y: y,
                        type: 'contour',
                        colorscale: maskColorScale,
                        showscale: false,
                        name: 'Mask',
                        hoverinfo: 'skip'
                    };

                    const data = [mapData, maskData];

                    // Výpočet rozsahů pro centrování a zachování poměru stran
                    const xMin = Math.min(...x);
                    const xMax = Math.max(...x);
                    const yMin = Math.min(...y);
                    const yMax = Math.max(...y);
                    const xRange = xMax - xMin;
                    const yRange = yMax - yMin;
                    const maxRange = Math.max(xRange, yRange);
                    const xMid = (xMin + xMax) / 2;
                    const yMid = (yMin + yMax) / 2;
                    const adjustedXRange = [xMid - maxRange / 2, xMid + maxRange / 2];
                    const adjustedYRange = [yMid - maxRange / 2, yMid + maxRange / 2];

                    const container = document.getElementById(divId);
                    const containerWidth = container.clientWidth;
                    const containerHeight = container.clientHeight;

                    const layout = {
                        width: containerWidth,
                        height: containerHeight,
                        margin: {
                            l: 30,
                            r: 30,
                            b: 60,
                            t: 30,
                            pad: 0
                        },
                        // paper_bgcolor: 'rgb(0,0,0,0)',
                        plot_bgcolor: 'white',
                        xaxis: {
                            range: adjustedXRange,
                            scaleanchor: 'y',
                            constrain: 'domain',
                            title: 'Distance x (pixels)',
                            automargin: true
                        },
                        yaxis: {
                            range: adjustedYRange,
                            constrain: 'domain',
                            title: 'Distance y (pixels)',
                            automargin: true
                        }
                    };

                    const config = {
                        responsive: true
                    };

                    try {
                        Plotly.purge(divId);
                        Plotly.newPlot(divId, data, layout, config);

                        document.getElementById("zmin").value = Math.round(mapData.zmin);
                        document.getElementById("zmax").value = Math.round(mapData.zmax);
                    } catch (error) {
                        console.error("An error during data interpolation:", error);
                        displayNoDataMessage(divId);
                    }
                },
                error: function(error) {
                    console.error("Chyba při načítání dat:", error);
                    alert(`Chyba při načítání dat: ${error}`);
                    displayNoDataMessage(divId);
                },
                complete: function() {
                    $('#spinner').hide();
                }
            });
        });
    });
}


plotSpatialWR('/contourplot_data', 'interp_chart');

function displayNoDataMessage(divId) {
    var data = [];
    var layout = {
        annotations: [
            {
                text: "The data cannot be dispayed",
                xref: "paper",
                yref: "paper",
                x: 0.5,
                y: 0.5,
                showarrow: false,
                font: {
                    size: 24,
                    color: "gray"
                }
            }
        ],
        xaxis: { visible: false },
        yaxis: { visible: false },
        plot_bgcolor: "white",
        paper_bgcolor: 'rgb(255,255,255,0)',
        showlegend: false,
    };
    Plotly.purge(divId);
    Plotly.newPlot(divId, data, layout);
}

// Funkce pro aktualizaci zmin a zmax hodnot na základě uživatelského vstupu
function updatePlot() {
    const spinner = document.getElementById("spinner");
    spinner.style.display = "block";  // požadujeme zobrazení

    setTimeout(() => {
        let newZmin = parseFloat(document.getElementById("zmin").value);
        let newZmax = parseFloat(document.getElementById("zmax").value);

        Plotly.restyle('interp_chart', { zmin: [newZmin], zmax: [newZmax] })
            .then(() => {
                spinner.style.display = "none";
            })
            .catch((error) => {
                console.error("Chyba při aktualizaci grafu:", error);
                spinner.style.display = "none";
            });
    }, 0);
}

function resetPlot() {
    document.getElementById("zmin").value = Math.round(originalZmin);
    document.getElementById("zmax").value = Math.round(originalZmax);
    updatePlot();  // Aktualizace grafu s výchozími hodnotami
}

window.addEventListener('resize', () => {
    const container = document.getElementById('interp_chart');
    Plotly.Plots.resize(container);
});