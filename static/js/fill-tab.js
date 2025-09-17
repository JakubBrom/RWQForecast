// Funkce pro načtení dat z backendu a vložení dat do tabulky
function loadData(getUrl, tabId, confId, selWr, selWq, selModel) {
    $(document).ready(function() {
        $(confId).click(function() {
            const osm_id = $(selWr).val();
            const feature = $(selWq).val();
            const wr_name = $(selWr + ' option:selected').text();
            const sel_date = $('#datepicker').val();
            const model_id = $(selModel).val();

            $.ajax({
                url: getUrl, // Endpoint na backendu
                method: "POST",
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature, wr_name: wr_name, sel_date: sel_date, model_id: model_id }),
                
                success: function(data) {
                    const tableBody = $(tabId);
                    tableBody.empty(); // Smazání stávajícího obsahu tabulky

                    data.forEach(row => {
                        let tableRow = `<tr><td>${row.info}</td>`;

                        if (!row.val2) {
                            // Pokud val2 je prázdné, spojíme buňky
                            tableRow += `<td colspan="2">${row.val1}</td>`;
                        } else {
                            tableRow += `<td>${row.val1}</td><td>${row.val2}</td>`;
                        }

                        tableRow += `</tr>`;
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
loadData("/data_info", "#tableBody", "#confirm-btn", "#sel_wr", "#select_wq", "#sel_model");
loadData("/data_spatial_info", "#tableBody2", "#interp-btn", "#sel_wr_sp", "#select_wq_sp", "#sel_model_sp");