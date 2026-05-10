function showError(message)
{
    document.getElementById("errorMessage").innerText = message;
    document.getElementById("errorModal").style.display = "flex";
}

function closeModal()
{
    document.getElementById("errorModal").style.display = "none";
}
