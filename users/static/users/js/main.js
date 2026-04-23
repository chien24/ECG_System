(function () {
    document.addEventListener("DOMContentLoaded", function () {
        const redirectNode = document.getElementById("logged-out-redirect");
        if (!redirectNode) return;

        const redirectUrl = redirectNode.dataset.redirectUrl;
        const delayMs = Number.parseInt(redirectNode.dataset.delayMs || "3000", 10);
        if (!redirectUrl) return;

        window.setTimeout(function () {
            window.location.href = redirectUrl;
        }, Number.isNaN(delayMs) ? 3000 : delayMs);
    });
})();
