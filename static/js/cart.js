// Auto-submit quantity form when input changes
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.cart-qty').forEach(function (input) {
    input.addEventListener('change', function () {
      this.closest('form').submit();
    });
  });
});
