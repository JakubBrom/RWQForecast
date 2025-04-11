// Frontend JS funkce pro předání dat

// Get data from the forms and add it to the backend

$(document).ready(function () {
    $('#downl-vect').click(function () {
        const osm_id = $('#sel_wr').val();
        const feature = $('#select_wq').val();
        const date = $('#datepicker').val();
        const model_id = $('#sel_model').val();
        const wr_name = $('#sel_wr option:selected').text();

        // Sestavení URL s parametry
        const url = `/download_gpkg?osm_id=${encodeURIComponent(osm_id)}&feature=${encodeURIComponent(feature)}&date=${encodeURIComponent(date)}&model_id=${encodeURIComponent(model_id)}&wr_name=${encodeURIComponent(wr_name)}`;

        // Přesměrování (spuštění stahování)
        window.location.href = url;
    });
});

