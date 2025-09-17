function selectModels(selectBtn, selectID, selectFeature, selectModel, routeUrl) {
    // Načtení dat pro výběr modelu v selectboxu
    $(document).ready(function(){
        $(selectBtn).change(function () {
            const osm_id = $(selectID).val();
            const feature = $(selectFeature).val();

            $.ajax({
                url: routeUrl,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature }),
                success: function(data) {
                    var data = JSON.parse(data);
                    // console.log(data);

                    // Vymazání předchozích možností
                    $(selectModel).empty() //.append('<option value="">Select prediction model</option>');

                    $.each(data, function(index, value) {
                        // Přidání nových možností do select boxu
                        $(selectModel).append('<option value="' + value.model_id + '">' + value.model_name + (value.is_default ? ' (default)' : '') + (value.osm_id ? ' (OSM_ID: ' + value.osm_id + ')' : '') + '</option>');
                        
                    });
                },
                error: function(error) {
                    $('#error').text('Došlo k chybě při načítání dat.');
                }
            });
        });
    });
}
selectModels('#sel_wr', '#sel_wr', '#select_wq', '#sel_model', '/set_models_to_selectBox');
selectModels('#select_wq', '#sel_wr', '#select_wq', '#sel_model', '/set_models_to_selectBox');
selectModels('#sel_wq', '#osm_id', '#sel_wq', '#sel_model','/set_models_to_selectBox');

//selectModels('#sel_wr_sp', '#sel_wr_sp', '#select_wq_sp', '#sel_model_sp', '/set_models_to_selectBox_existing');
selectModels('#select_wq_sp', '#sel_wr_sp', '#select_wq_sp', '#sel_model_sp', '/set_models_to_selectBox_existing');