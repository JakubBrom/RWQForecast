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
    window.location.href = data.url;  // Přesměrování na danou URL
});