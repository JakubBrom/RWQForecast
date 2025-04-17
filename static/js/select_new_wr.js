document.addEventListener('DOMContentLoaded', function() { // Důležité!

    var map = L.map('map').setView([48.8, 14.8], 5);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    let confirmListener = null;
    let selectedLayer = null;

    var waterBodiesLayer = L.geoJSON(null, {
        style: function () {
            return { color: "blue", weight: 4 };
        },
        onEachFeature: function (feature, layer) {
            layer.bindPopup("Name: " + (feature.properties.name || "Noname") + "<br>" +
                            "OSM_ID: " + (feature.properties.osm_id || null)
            );

            layer.on('click', function () {
                if (selectedLayer) {
                    waterBodiesLayer.resetStyle(selectedLayer);
                }
                selectedLayer = this;
                this.setStyle({ color: "red" });

                document.getElementById("osm_id").value = feature.properties.osm_id;
                document.getElementById("name").value = feature.properties.name;
                document.getElementById("sel_wq").value = ""; // Reset parametru kvality vody do inputu
                document.getElementById("sel_model").value = ""; // Reset selektovaného modelu do inputu
            });
        }
    }).addTo(map);

    const loadingIndicator = document.getElementById("loading");

    function showLoading() {
        loadingIndicator.style.display = "block";
    }

    function hideLoading() {
        loadingIndicator.style.display = "none";
    }

    function loadWaterBodies() {
        const currentZoom = map.getZoom();  
        var geojsonData = null;
        waterBodiesLayer.clearLayers();
        console.log("Current zoom is " + currentZoom);  
        if (currentZoom < 11) {                              
            if (geojsonData) {
                waterBodiesLayer.clearLayers();
                geojsonData = null;
            }
            return;
        }
        var bounds = map.getBounds();
        var bbox = {
            south: bounds.getSouthWest().lat,
            west: bounds.getSouthWest().lng,
            north: bounds.getNorthEast().lat,
            east: bounds.getNorthEast().lng
        };

        showLoading(); // Zobrazit ukazatel načítání

        var overpassUrl = "https://overpass-api.de/api/interpreter";
        var overpassQuery = `
            [out:json][timeout:25];
            (
            way["natural"="water"](${bbox.south}, ${bbox.west}, ${bbox.north}, ${bbox.east});
            relation["natural"="water"](${bbox.south}, ${bbox.west}, ${bbox.north}, ${bbox.east});
            );                
            convert item ::=::,::geom=geom(),_osm_type=type(),_id=id();
            out geom;
        `;

        fetch(overpassUrl, {
            method: "POST",
            body: overpassQuery,
            headers: { "Content-Type": "text/plain" }
        })
            .then(response => response.json())
            .then(data => {
                geoJsonData = {
                    type: "FeatureCollection",
                    features: data.elements
                    .filter(el => el.geometry) // Pouze prvky s geometrií
                    .flatMap(el => {
                        // Rozdělíme geometrie podle typu
                        if (el.geometry.type === "GeometryCollection") {
                            return el.geometry.geometries.map(geom => ({
                                type: "Feature",
                                properties: { 
                                    name: el.tags.name || "Noname",
                                    osm_id: el.tags._id || null
                                },
                                geometry: geom // Přidáme každou geometrii samostatně
                            }));
                        } else {
                            return {
                                type: "Feature",
                                properties: { 
                                    name: el.tags.name || "Noname",
                                    osm_id: el.tags._id || null
                                },
                                geometry: el.geometry // Standardní geometrie
                            };
                        }
                    })
            };
            
            waterBodiesLayer.addData(geoJsonData); // Přidání dat do mapy
            })
            .catch(error => console.error("Error during reading data from Overpass API:", error))
            .finally(() => hideLoading()); // Skrytí ukazatele načítání
    }

    map.on('moveend', loadWaterBodies);
    loadWaterBodies();

    // Získání prvků dialogu a nastavení posluchačů UDÁLOSTÍ ZDE!
    const confirmButton = document.getElementById("confirm-btn-processing");
    const prekryti = document.getElementById("prekryti");
    const dialog = document.getElementById("dialog");
    const souhrnInformaci = document.getElementById("souhrnInformaci");
    const potvrditDialog = document.getElementById("potvrditDialog");
    const zrusitDialog = document.getElementById("zrusitDialog");

    // Skrytí dialogu na začátku
    prekryti.style.display = "none";

    confirmButton.addEventListener("click", function() {
        if (selectedLayer) {
            souhrnInformaci.textContent = "Confirm the analysis for the reservoir: " + document.getElementById("name").value + " (OSM ID: " + document.getElementById("osm_id").value + ")?";
            prekryti.style.display = "flex";
        } else {
            alert("Select the water reservoir first");
        }
    });

    potvrditDialog.addEventListener("click", function() {
        if (selectedLayer) {
            var osm_id = document.getElementById("osm_id").value;
            var wname = document.getElementById("name").value;
            var wq_par = document.getElementById("sel_wq").value;
            const vertices = selectedLayer.getLatLngs();
            const firstVertex = vertices[0];
            const model_id = document.getElementById("sel_model").value; // Získání ID modelu z inputu

            // Uzavření dialogu IHNED po kliknutí na "Potvrdit"
            prekryti.style.display = "none";

            // // PŘESMĚROVÁNÍ IHNED PO POTVRZENÍ --> posunout o kus dál až po stažení vrstvy a výpočtu plochy --> načíst plochu a buď vypsat, že je plocha malá nebo je v DB a nebo spustit proces výpočtu.
            // window.location.href = "/processing?osm_id=" + osm_id; // Přesměrování s parametrem

            fetch('/select_waterbody', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ osm_id: osm_id, name: wname, wq_param: wq_par, firstVrt: firstVertex, model_id: model_id })
            })
                .then(response => response.json())
                .then(data => {                            
                    console.log("Backend process finished:", data);
                    socket.emit("select_and_start_analysis", { osm_id: osm_id });
                })
                .catch(error => {
                    console.error("Error during sending the data", error);
                    //alert("The error during sending the data to the server has occured");
                    prekryti.style.display = "none";
                });
        }
    });

    zrusitDialog.addEventListener("click", function() {
        prekryti.style.display = "none";
    });
}); // Konec události DOMContentLoaded