// Načtení dat pro výběr nádrže
$(document).ready(function(){
    $.ajax({
        url: '/set_wr_to_selectBox',
        type: 'GET',
        success: function(response) {
            var data = JSON.parse(response);
            $.each(data, function(index, value) {
                $('#sel_wr').append('<option value="' + value.osm_id + '">' + value.name + '</option>');
            });
        },
        error: function(error) {
            $('#error').text('Došlo k chybě při načítání dat.');
        }
    });
});