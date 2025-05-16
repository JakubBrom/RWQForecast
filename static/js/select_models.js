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
                    console.log('Data for models OK:', data);
                    var data = JSON.parse(data);

                    // Vymazání předchozích možností
                    $(selectModel).empty() //.append('<option value="">Select prediction model</option>');

                    $.each(data, function(index, value) {
                        // Přidání nových možností do select boxu
                        if (value.is_default == true) {                                
                            if (value.osm_id == null) {
                                $(selectModel).append('<option value="' + value.model_id + '">' + value.model_name + ' (default)' + '</option>');
                            }
                            else {
                                $(selectModel).append('<option value="' + value.model_id + '">' + value.model_name + ' (OSM_ID: ' + value.osm_id + '; default)' + '</option>');
                            }
                        }
                        else {
                            if (value.osm_id == null) {
                                $().append('<option value="' + value.model_id + '">' + value.model_name + '</option>');
                            }
                            else {
                                $(selectModel).append('<option value="' + value.model_id + '">' + value.model_name + ' (OSM_ID: ' + value.osm_id + ')' + '</option>');
                            }
                        }
                        
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