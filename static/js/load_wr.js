//Funkcionalita mapy
var myMap = L.map('map_result').setView([48.8, 14.8], 5);
window.myMap = myMap;

// Základní vrstva OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(myMap);

let selectedLayer = null;

var waterBodiesLayer = L.geoJSON(null, {
    style: function () {
        return { color: "blue", weight: 2};
    },
    onEachFeature: function (feature, layer) {
        layer.bindPopup("Name: " + (feature.properties.name || "Noname") + "<br>" +
                        "OSM_ID: " + (feature.properties.osm_id || null) + "<br>" +
                        "Area: " + (feature.properties.area || null) + " ha"
        );

        layer.on('click', function () {
            if (selectedLayer) {
                waterBodiesLayer.resetStyle(selectedLayer);
            }
            selectedLayer = this;
            this.setStyle({ color: "red" });

            document.getElementById("sel_wr").value = feature.properties.osm_id;
        });
    }
}).addTo(myMap);

// Dynamické načítání GeoJSON dat
function loadWaterBodies() {
        waterBodiesLayer.clearLayers();
        var currentZoom = myMap.getZoom();
        console.log("Aktuální zoom úroveň:", currentZoom);
        var geojsonData = null;

        // Získání aktuálního rozsahu mapy
        const bounds = myMap.getBounds();
        const bbox = {
            south: bounds.getSouth(),
            west: bounds.getWest(),
            north: bounds.getNorth(),
            east: bounds.getEast()
        };

        fetch('/add_wr_to_map', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bbox)
        })
        .then(response => response.json())
        .then(data => {
            geoJsonData = data;
            L.geoJSON(data, {}).addTo(myMap);
        console.log("Data načtena:", data.elements);
        waterBodiesLayer.addData(data);    
    });
}
myMap.on("moveend", loadWaterBodies);
loadWaterBodies();