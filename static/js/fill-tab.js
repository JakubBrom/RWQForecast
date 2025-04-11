// Funkce pro načtení dat z backendu a vložení dat do tabulky
function loadData(getUrl, tabId, confId) {
    $(document).ready(function() {
        $(confId).click(function() {
            const osm_id = $('#sel_wr').val();
            const feature = $('#select_wq').val();
            const wr_name = $('#sel_wr option:selected').text();
            const sel_date = $('#datepicker').val();
            const model_id = $('#sel_model').val();

            $.ajax({
                url: getUrl, // Endpoint na backendu
                method: "POST",
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, wr_name: wr_name, sel_date: sel_date, model_id: model_id }),
                success: function(data) {
                    const tableBody = $(tabId);
                    tableBody.empty(); // Smazání stávajícího obsahu tabulky

                    // Iterace přes přijatá data a jejich přidání do tabulky
                    data.forEach(row => {
                        const tableRow = `
                            <tr>
                                <td>${row.info}</td>
                                <td>${row.val1}</td>
                                <td>${row.val2}</td>
                            </tr>
                        `;
                        tableBody.append(tableRow);
                    });
                },
                error: function(error) {
                    console.error("Error loading data:", error);
                }
            });
        });
    });
}

// Event listener pro tlačítko
loadData("/data_info", "#tableBody", "#confirm-btn");
loadData("/data_spatial_info", "#tableBody2", "#interp-btn");