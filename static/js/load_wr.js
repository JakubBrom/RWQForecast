// Funkcionalita mapy
var myMap = L.map('map_result').setView([48.8, 14.8], 5);
window.myMap = myMap;

// Základní vrstva OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(myMap);

function addInteractiveGeoLayer(options) {
    const {
        map,
        geoJsonUrl,
        inputSelector,
        style = { color: "blue", weight: 2 },
        highlightStyle = { color: "red", weight: 2 },
        getId = f => f.properties.osm_id,
        getPopup = f => `Name: ${f.properties.name || "Noname"}<br>OSM_ID: ${f.properties.osm_id || "?"}<br>Area: ${f.properties.area || "?"}`
    } = options;

    let selectedLayer = null;
    let geoJsonData = null;
    let userTriggered = true;

    const inputEl = document.querySelector(inputSelector);
    if (!inputEl) {
        console.error(`Input feature '${inputSelector}' not found.`);
        return;
    }

    const layerGroup = L.geoJSON(null, {
        style: () => style,
        onEachFeature: function (feature, layer) {
            const id = getId(feature);
            layer.bindPopup(getPopup(feature));

            layer.on('click', function () {
                highlightFeature(layer, id);
            });
        }
    }).addTo(map);

    function highlightFeature(layer, id) {
        if (selectedLayer) {
            layerGroup.resetStyle(selectedLayer);
        }
        selectedLayer = layer;
        layer.setStyle(highlightStyle);
        inputEl.value = id;
    }

    inputEl.addEventListener("change", function () {
        const val = this.value;
        if (!geoJsonData) return;

        let found = false;
        layerGroup.eachLayer(function (layer) {
            const feature = layer.feature;
            if (feature && String(getId(feature)) === val) {
                userTriggered = false;
                map.fitBounds(layer.getBounds());
                highlightFeature(layer, getId(feature));
                setTimeout(() => userTriggered = true, 500);  // Obnovíme po půl vteřině
                found = true;
            }
        });

        if (!found) {
            alert(`Feature ID ${val} not found.`);
        }
    });

    function loadData() {
        layerGroup.clearLayers();
        const bounds = map.getBounds();
        const bbox = {
            south: bounds.getSouth(),
            west: bounds.getWest(),
            north: bounds.getNorth(),
            east: bounds.getEast()
        };

        const dataPromise = typeof geoJsonUrl === "function" ? geoJsonUrl(bbox) : fetch(geoJsonUrl).then(r => r.json());

        dataPromise.then(data => {
            geoJsonData = data;
            layerGroup.addData(data);
            console.log("Načtena data:", data);
        });
    }

    map.on("moveend", () => {
        if (userTriggered) {
            loadData();
        }
    });

    loadData();

    return {
        layer: layerGroup,
        reload: loadData
    };
}

// Pokud #sel_wr neexistuje, potom použijeme #sel_wr_sp
var selWr = "#sel_wr";
if (!document.querySelector(selWr)) {
    selWr = "#sel_wr_sp";
}

addInteractiveGeoLayer({
    map: myMap,
    geoJsonUrl: (bbox) => fetch('/add_wr_to_map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bbox)
    }).then(r => r.json()),
    inputSelector: selWr,
    getId: f => f.properties.osm_id,
    getPopup: f => `Name: ${f.properties.name || 'Noname'}<br>OSM ID: ${f.properties.osm_id}<br>Area: ${f.properties.area}`
});
