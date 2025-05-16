// Zazoomování mapy na vybraný objekt
function zoomMapToPolygon(dataUrl, selBox){
    // dataUrl: URL pro získání dat z backendu
    // divId: ID divu, do kterého se graf vykreslí
    $(document).ready(function() {
        $(selBox).change(function() {
            const osm_id = $(selBox).val();

            $.ajax({
                url: dataUrl,  // Endpoint na backendu
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ osm_id: osm_id }),
                success: function(data) {
                    console.log('Data received:', data);

                    var southWest = L.latLng(data.southWest.lat, data.southWest.lng);
                    var northEast = L.latLng(data.northEast.lat, data.northEast.lng);
                    var bounds = L.latLngBounds(southWest, northEast);
                    myMap.fitBounds(bounds);
                },
                error: function(err) {
                    console.error('Error zooming map', err);
                },
            });
        });
    });
};

zoomMapToPolygon('/get_bounds', '#sel_wr')
zoomMapToPolygon('/get_bounds', '#sel_wr_sp')