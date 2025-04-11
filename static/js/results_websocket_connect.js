// Připojení k WebSocket serveru
var socket = io.connect('http://' + document.domain + ':' + location.port);

// Naslouchání zprávám
socket.on("flash_message", function(data) {
    console.log("Zpráva: ", data);

    // Vytvoření flash zprávy
    const flashMessage = $(`
        <div class="alert alert-${data.category} alert-dismissible fade show" role="alert">
            ${data.message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `);

    // Přidání zprávy do divu
    $("#flash-messages").append(flashMessage);

    // Automatické skrytí zprávy po 5 sekundách
    setTimeout(function() {
        flashMessage.fadeOut(500, function() { $(this).remove(); });
    }, 10000);
});

socket.on("redirect", function(data) {
    sessionStorage.setItem("flashMessage", data.message);
    window.location.href = data.url;  // Přesměrování na danou URL
});

// Odeslání požadavku na spuštění analýzy
$(document).ready(function() {
    $("#update-btn").click(function() {
        const osm_id = $('#sel_wr').val();
        const feature = $('#select_wq').val();
        const wr_name = $('#sel_wr option:selected').text();

        socket.emit("start_analysis", {osm_id: osm_id, feature: feature, wr_name: wr_name});
    });
});