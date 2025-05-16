let flatpickrInstance;
let lastUsedKey = "";

function fillDatepicker(dataUrl, selWr, selFc, selModel) {
$(document).ready(function () {
    flatpickrInstance = flatpickr("#datepicker", {
    dateFormat: "Y-m-d",
    altInput: true,
    altFormat: "d.m.Y",
    disableMobile: true,

    onOpen: function (selectedDates, dateStr, instance) {
        const osm_id = $(selWr).val();
        const feature = $(selFc).val();
        const model_id = $(selModel).val();

        if (!osm_id || !feature || !model_id) {
        console.warn("Chybějící vstupy pro získání dostupných dat.");
        return;
        }

        const currentKey = `${osm_id}-${feature}-${model_id}`;
        const isFirstLoad = (currentKey !== lastUsedKey);
        lastUsedKey = currentKey;

        $.ajax({
        url: dataUrl,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            osm_id: osm_id,
            feature: feature,
            model_id: model_id
        }),
        success: function (data) {
            console.log('Data received:', data);

            const availableSet = new Set(data); // očekáváme ['YYYY-MM-DD']

            if (isFirstLoad && data.length > 0) {
            const lastDate = data[data.length - 1];
            instance.setDate(lastDate, false);
            }

            instance.set('onDayCreate', function (dObj, dStr, fp, dayElem) {
            const dateStr = fp.formatDate(dayElem.dateObj, "Y-m-d");
            if (availableSet.has(dateStr)) {
                dayElem.classList.add("available-date");
            }
            });

            instance.redraw();
        },
        error: function (err) {
            console.error('Chyba při získávání dat dostupných termínů', err);
        }
        });
    }
    });
});
}

fillDatepicker('/available-dates', '#sel_wr_sp', '#select_wq_sp', '#sel_model_sp');

