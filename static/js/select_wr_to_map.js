function selectWrToSelectBox(selectBoxWr) {
    // Načtení dat pro výběr nádrže
    $(document).ready(function(){
        $.ajax({
            url: '/set_wr_to_selectBox',
            type: 'GET',
            success: function(response) {
                var data = JSON.parse(response);
                $.each(data, function(index, value) {
                    $(selectBoxWr).append('<option value="' + value.osm_id + '">' + value.name + '</option>');
                });
            },
            error: function(error) {
                $('#error').text('Došlo k chybě při načítání dat.');
            }
        });
    });
}    
    
selectWrToSelectBox('#sel_wr');
selectWrToSelectBox('#sel_wr_sp');