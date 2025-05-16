// Načtení dat pro interpolaci a vytvoření heatmapy
function plotSpatialWR(dataUrl, divId){
    // dataUrl: URL pro získání dat z backendu
    // divId: ID divu, do kterého se graf vykreslí
    $(document).ready(function() {
        $('#interp-btn').click(function() {
            const osm_id = $('#sel_wr_sp').val();
            const feature = $('#select_wq_sp').val();
            const date = $('#datepicker').val();
            const model_id = $('#sel_model_sp').val(); // Přidání model_id pro stažení vektorů

            $('#spinner').show();
            $('#sp_results').show(); // Zobrazení grafu
            $('#controls').show(); // Zobrazení inputu pro zmin a zmax
            $('#downl-vect-text').show(); // Zobrazení textu pro stažení vektorů
            $('#downl-vect').show(); // Zobrazení tlačítka pro stažení vektorů

            $.ajax({
                url: dataUrl,  // Endpoint na backendu
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, date: date, model_id: model_id }),
                success: function(response) {
                    console.log(response);
                    const x = response.x;  // Osa X
                    const y = response.y;  // Osa Y
                    const z = response.z;  // 2D matice
                    const m = response.m;   // 2D matice pro masku

                    // Definice custom colorscale s úpravou hodnoty 0
                    const customColorscale = [
                    [0, 'rgb(0, 12, 140)'],
                    [0.5, 'rgb(228, 245, 104)'],
                    [1, 'rgb(7, 125, 25)']
                    ];                    

                    const maskColorScale = [
                    [0, 'white'],
                    [1, 'white']
                    ];

                    // Hodnoty pro zmin a zmax
                    originalZmin = Math.min(...z.flat()); // Dynamické minimum
                    originalZmax = Math.max(...z.flat()); // Dynamické maximum

                    // Vykreslení heatmapy/contour mapy
                    const mapData = {
                        z: z,
                        x: x,
                        y: y,
                        //zsmooth: 'best',
                        //type: 'heatmap',
                        connectgaps: true,
                        type: 'contour',
                        line:{
                            smoothing: 0.85,
                            color: 'rgb(150,150,150)'
                          },
                        colorscale: customColorscale,                        
                        zmin: Math.min(...z.flat()), // Dynamické minimum
                        zmax: Math.max(...z.flat()), // Dynamické maximum
                        name: 'Data',
                        //zmin: 0,
                        //zmax: 600,
                        hovertemplate: '%{z:.2f}<extra></extra>',
                        colorbar:{
                            title:{text:'Concentration',
                            side: 'right',   
                            },
                            len: 0.8,
                        }
                    };

                    const maskData = {
                        z: m,
                        x: x,
                        y: y,
                        type: 'contour',
                        colorscale: maskColorScale,
                        //colorbar: {title: ',a,nm,amsndnm,a'},
                        //zmin: Math.min(...z.flat()), // Dynamické minimum
                        //zmax: Math.max(...z.flat()), // Dynamické maximum
                        showscale: false,
                        name: 'Mask',
                        hoverinfo: 'skip',
                    };

                    const data = [mapData, maskData];

                    const numCols = x.length;
                    const numRows = y.length;

                    const container = document.getElementById(divId);
                    const containerWidth = container.clientWidth;
                    const containerHeight = container.clientHeight;
                    //const aspectRatio = numRows / numCols;
                    //const calculatedHeight = containerWidth * aspectRatio;

                    const layout = {                       
                        xaxis: {
                            scaleanchor: 'y', // Ujistí se, že osy x a y mají stejné měřítko
                            constrain: 'domain', // Zachová rozsah osy x
                            title: 'Distance x (pixels)'
                          },
                          yaxis: {
                            constrain: 'domain', // Zachová rozsah osy y
                            title: 'Distance y (pixels)'
                          },
                        width: containerWidth,
                        height: containerHeight,
                        margin: {
                            l: 30,
                            r: 30,
                            b: 30,
                            t: 30,
                            pad: 0
                        },
                        paper_bgcolor: 'rgb(255,255,255,0)',
                    };

                    const config = {
                        responsive: true
                      };

                    //Plotly.newPlot(divId, data, layout);
                    try {
                        
                        Plotly.purge(divId);
                        Plotly.newPlot(divId, data, layout, config);

                        // Získání hodnot pro zmin a zmax z dat
                        document.getElementById("zmin").value = Math.round(mapData.zmin);
                        document.getElementById("zmax").value = Math.round(mapData.zmax);

                    } catch (error) {
                        console.error("An error during data intepolation:", error);
                        displayNoDataMessage(divId);
                    }
                },
                error: function(error) {
                    console.error("Chyba při načítání dat:", error);
                    alert(`Chyba při načítání dat: ${error}`);

                    var data = [];

                    var layout = {
                        annotations: [
                            {
                            text: "No Data",
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

                    // Zobrazení grafu v HTML elementu s id 'plot'
                    Plotly.purge(divId);
                    Plotly.newPlot(divId, data, layout);
                },
                complete: function() {  
                    $('#spinner').hide();  // Skryje spinner po načtení
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