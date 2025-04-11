function selectModels(selectBtn, selectID, selectFeature) {
    // Načtení dat pro výběr modelu v selectboxu
    $(document).ready(function(){
        $(selectBtn).change(function () {
            const osm_id = $(selectID).val();
            const feature = $(selectFeature).val();

            $.ajax({
                url: '/set_models_to_selectBox',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id, feature: feature }),
                success: function(data) {
                    console.log('Data for models OK:', data);
                    var data = JSON.parse(data);

                    // Vymazání předchozích možností
                    $('#sel_model').empty() //.append('<option value="">Select prediction model</option>');

                    $.each(data, function(index, value) {
                        // Přidání nových možností do select boxu
                        if (value.is_default == true) {                                
                            if (value.osm_id == null) {
                                $('#sel_model').append('<option value="' + value.model_id + '">' + value.model_name + ' (default)' + '</option>');
                            }
                            else {
                                $('#sel_model').append('<option value="' + value.model_id + '">' + value.model_name + ' (OSM_ID: ' + value.osm_id + '; default)' + '</option>');
                            }
                        }
                        else {
                            if (value.osm_id == null) {
                                $('#sel_model').append('<option value="' + value.model_id + '">' + value.model_name + '</option>');
                            }
                            else {
                                $('#sel_model').append('<option value="' + value.model_id + '">' + value.model_name + ' (OSM_ID: ' + value.osm_id + ')' + '</option>');
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
selectModels('#sel_wr', '#sel_wr', '#select_wq');
selectModels('#select_wq', '#sel_wr', '#select_wq');
selectModels('#sel_wq', '#osm_id', '#sel_wq');