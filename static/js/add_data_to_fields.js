// Vložení názvu nádrže do inputu #wr_selected ze select boxu #select_wq po kliknutí na tlačítko #confirm-btn
$(document).ready(function() {
    $('#confirm-btn').click(function() {
        const wr_name = $('#sel_wr option:selected').text();
        $('#wr_selected').val(wr_name);

        $('#ts_results').show();
        $('#downl_ts_text').show();
        $('#downl-ts').show();
        $('#downl-fc').show();
        document.getElementById('ts_results').scrollIntoView({ behavior: 'smooth' });
    });
});