document.addEventListener("DOMContentLoaded", () => {
  // Auto-dismiss alerts after 5 seconds
  document.querySelectorAll(".flash-area .alert").forEach((el) => {
    setTimeout(() => {
      bootstrap.Alert.getOrCreateInstance(el).close();
    }, 5000);
  });

  // Registration: check passwords match before submitting
  const form = document.getElementById("registerForm");
  if (form) {
    form.addEventListener("submit", (e) => {
      const p = form.querySelector("#password").value;
      const c = form.querySelector("#confirm_password").value;
      if (p !== c) {
        e.preventDefault();
        alert("Passwords do not match.");
      }
    });
  }

  // Date pickers: check-out must be at least the day after check-in
  const checkIn = document.getElementById("check_in");
  const checkOut = document.getElementById("check_out");
  if (checkIn && checkOut) {
    const nextDay = (value) => {
      const d = new Date(value + "T00:00:00");
      d.setDate(d.getDate() + 1);
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    };
    const sync = () => {
      if (!checkIn.value) return;
      const min = nextDay(checkIn.value);
      checkOut.min = min;
      if (!checkOut.value || checkOut.value < min) checkOut.value = min;
    };
    checkIn.addEventListener("change", sync);
  }
});