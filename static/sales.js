// Sale Order form helpers (convenience only - the server recalculates totals itself).
//  1. When an Item Code is chosen, fill in that item's price.
//  2. Whenever Quantity or Unit Price changes, update Sub Total and Total.
(function () {
  const prices = JSON.parse(document.getElementById("prices").textContent);
  const $ = (id) => document.getElementById(id);
  const itemCode = $("item_code"), qty = $("quantity"), unit = $("unit_price");
  const subTotal = $("sub_total"), total = $("total");

  function recalc() {
    const q = parseInt(qty.value, 10), p = parseFloat(unit.value);
    const sum = q > 0 && p >= 0 ? (q * p).toFixed(2) : "";
    subTotal.value = sum;
    total.value = sum;
  }

  function fillPrice() {
    if (prices[itemCode.value] !== undefined) {
      unit.value = prices[itemCode.value];
      recalc();
    }
  }

  itemCode.addEventListener("change", fillPrice);
  itemCode.addEventListener("input", fillPrice);
  qty.addEventListener("input", recalc);
  unit.addEventListener("input", recalc);
  recalc();
})();
