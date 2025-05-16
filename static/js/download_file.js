// Frontend JS funkce pro předání dat a stažení souboru

// Get data from the forms and download the file
function downloadData(downlBtn, downloadUrl, selWr, selectWq, datePicker, selModel) {
    $(document).ready(function () {
        $(downlBtn).click(function () {
            const osm_id = $(selWr).val();
            const feature = $(selectWq).val();
            const date = $(datePicker).val();
            const model_id = $(selModel).val();
            const wr_name = $(selWr + ' option:selected').text();

            // Sestavení URL s parametry
            const url = `/${downloadUrl}?osm_id=${encodeURIComponent(osm_id)}&feature=${encodeURIComponent(feature)}&date=${encodeURIComponent(date)}&model_id=${encodeURIComponent(model_id)}&wr_name=${encodeURIComponent(wr_name)}`;

            // Přesměrování (spuštění stahování)
            window.location.href = url;
        });
    });
}

downloadData('#downl-vect', 'download_gpkg', '#sel_wr_sp', '#select_wq_sp', '#datepicker', '#sel_model_sp')
downloadData('#downl-ts', 'download_ts', '#sel_wr', '#select_wq', '#datepicker', '#sel_model')