const AUTO_CAPITALIZE_FIELDS = new Set([
  "customer_group_name",
  "customer_name",
  "site_name",
  "project_group_name",
  "department",
  "contact_name",
  "po_customer_name",
  "equipment_name",
  "project_name",
]);
const ACRONYMS = new Set(["abc", "dcps", "eolt", "fat", "mty", "npi", "po", "qa", "rfq", "sbd"]);

function smartCapitalize(value) {
  return String(value || "").replace(/\b([A-Za-z][A-Za-z0-9-]*)\b/g, (word) => {
    const lower = word.toLowerCase();
    if (ACRONYMS.has(lower)) return word.toUpperCase();
    return word.charAt(0).toUpperCase() + word.slice(1);
  });
}

function normalizeTextInputs(form) {
  AUTO_CAPITALIZE_FIELDS.forEach((name) => {
    const input = form.elements[name];
    if (input && typeof input.value === "string") {
      input.value = smartCapitalize(input.value.trim());
    }
  });
}
