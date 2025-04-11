
// Fce pro vykreslení časové řady pomocí Plotly
function plotTimeSeries(dataUrl, divId){
    // dataUrl: URL pro získání dat z backendu
    // divId: ID divu, do kterého se graf vykreslí
    $(document).ready(function() {
        $('#confirm-btn').click(function() {
            const osm_id = $('#sel_wr').val();
            const feature = $('#select_wq').val();
            const model_id = $('#sel_model').val();

            $('#ts_chart').show();
            $('#forecast_chart').show();

            $.ajax({
                url: dataUrl,  // Endpoint na backendu
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, model_id: model_id }),
                success: function(response) {
                    console.log('Data received:', response.data);
                    const data = response.data;

                    // Připrav data pro Plotly
                    const x = data.map(d => d.date);
                    const meanLine = data.map(d => d.mean || null);
                    const medianLine = data.map(d => d.median || null);
                    const ciLower = data.map(d => d.ci_lower || null);
                    const ciUpper = data.map(d => d.ci_upper || null);

                    // Vykresli graf
                    const traceMean = {
                        x: x,
                        y: meanLine,
                        mode: 'lines',
                        type: 'scatter',
                        name: 'Mean',
                        line: {
                            color: 'green',
                            width: 2,
                            //shape: 'spline',
                        }
                    };

                    const traceMedian = {
                        x: x,
                        y: medianLine,
                        mode: 'lines',
                        type: 'scatter',
                        name: 'Median',
                        line: {
                            color: 'blue',
                            width: 1,
                            //shape: 'spline',
                        }
                    };

                    const traceCILower = {
                        x: x,
                        y: ciLower,
                        mode: 'lines',
                        type: 'scatter',
                        name: 'Conf. Interval Lower',
                        line: {
                            color: 'grey',
                            width: 0.5,
                            //shape: 'spline',
                        }
                    };

                    const traceCIUpper = {
                        x: x,
                        y: ciUpper,
                        mode: 'lines',
                        type: 'scatter',
                        name: 'Conf. Interval Upper',
                        line: {
                            color: 'grey',
                            width: 0.5,
                            //shape: 'spline',
                        }
                    };

                    // Vykresli graf
                    Plotly.newPlot(divId, [traceMean, traceMedian, traceCILower, traceCIUpper], {
                        xaxis: {
                            title: {
                                text: 'Date'
                            }
                        },
                        yaxis: { 
                            title: {
                                text: 'Concentration of ' + feature + ' (&mu;g&#x2219;l<sup>-1</sup>)'
                            }
                        },
                        legend: {
                            orientation: 'h',
                            x: 1,
                            y: 1.2,
                            xanchor: 'right',
                            yanchor: 'top'
                        }
                    });
                    
                },
                error: function(err) {
                    console.error('Error fetching data:', err);
                },
            });
        });

        // Jednoduchá implementace LOESS (pro ilustraci)
        function loess(x, y) {
            // Načítání knihovny pro LOESS (pokud je potřeba).
            return y; // Placeholder
        }
    });
}

plotTimeSeries('/ts_data', 'ts_chart');
plotTimeSeries('/forecast_data', 'forecast_chart');