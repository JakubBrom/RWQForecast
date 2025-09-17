function showWQFeaturePopoverInfo(myBtn, selectFeature) {
    // Provide info about water quality features in a popover
    // when the user clicks on the button

    $(document).ready(function () {
        $(myBtn).popover({
            trigger: 'click',
            html: true,
            // title: function () {
            //     return '<div id="popover-title">Loading...</div>';
            // },
            content: function () {
                return '<div id="popover-content">Loading...</div>';
            }
        });

        // Dynamické načtení obsahu do popoveru při jeho zobrazení
        $(myBtn).on('shown.bs.popover', function () {

            // Získání aktuální hodnoty ze selectboxu při kliknutí
            const feature = $(selectFeature).val();

            $.ajax({
                url: '/get_wqfeature_info',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ feature: feature}),
                success: function (data) {
                    const feature = data.feature;
                    const description = data.description;
                    console.log('Feature:', feature);
                    console.log('Description:', description);

                    //$('#popover-title').html('Water quality feature information: ' + feature);
                    $('#popover-content').html(description);
                },
                error: function () {
                    $('#popover-content').html('Error loading content: Select the water quality feature first.');
                }
            });
        });

        // Zavření popoveru při kliknutí mimo něj
        $(document).on('click', function (e) {
            var popover = $(myBtn);
            if (!popover.is(e.target) && popover.has(e.target).length === 0 &&
                $('.popover').has(e.target).length === 0) {
                popover.popover('hide');
            }
        });
    });
}

showWQFeaturePopoverInfo('#select_wq_info_sp', '#select_wq_sp');
showWQFeaturePopoverInfo('#select_wq_info_ts', '#select_wq');
showWQFeaturePopoverInfo('#select_wq_info_add', '#sel_wq');