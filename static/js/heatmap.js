// Načtení dat pro interpolaci a vytvoření heatmapy
function plotTimeSeries(dataUrl, divId){
    // dataUrl: URL pro získání dat z backendu
    // divId: ID divu, do kterého se graf vykreslí
    $(document).ready(function() {
        $('#interp-btn').click(function() {
            const osm_id = $('#sel_wr').val();
            const feature = $('#select_wq').val();
            const date = $('#datepicker').val();

            $('#spinner').show();

            $.ajax({
                url: dataUrl,  // Endpoint na backendu
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, date: date }),
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
                        //zmin: Math.min(...z.flat()), // Dynamické minimum
                        //zmax: Math.max(...z.flat()), // Dynamické maximum
                        name: 'Data',
                        zmin: 0,
                        zmax: 600,
                        hovertemplate: '%{z:.2f}<extra></extra>',
                        colorbar:{
                            title:{text:'Concentration',
                            side: 'right'    
                            },                               
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

                    const numRows = x.Length;
                    const numCols = y.Length;

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
                        width: numCols,  // Šířka grafu
                        height: numRows, // Výška grafu
                        margin: {
                            l: 30,
                            r: 30,
                            b: 30,
                            t: 30,
                            pad: 5
                        },
                        paper_bgcolor: 'rgb(255,255,255,0)',
                    };

                    Plotly.newPlot(divId, data, layout);
                },
                error: function(error) {
                    console.error("Chyba při načítání dat:", error);
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
                    showlegend: false
                    };

                    // Zobrazení grafu v HTML elementu s id 'plot'
                    Plotly.newPlot(divId, data, layout);
                },
                complete: function() {  
                    $('#spinner').hide();  // Skryje spinner po načtení
                }
            });
        });
    });
}

plotTimeSeries('/interpolate_data', 'interp_chart');