const details = document.querySelector('#details');
if (details) {
  const updateCounter = () => { document.querySelector('#counter').textContent = `${details.value.length}/2000`; };
  details.addEventListener('input', updateCounter);
  updateCounter();
}
const form = document.querySelector('[data-request-form]');
if (form) {
  // Пробелы не должны проходить как заполненное обязательное поле.
  for (const field of form.querySelectorAll('[required]')) {
    const validate = () => {
      const minimum = Number(field.getAttribute('minlength')) || 1;
      field.setCustomValidity(field.value.trim().length < minimum ? `Введите не меньше ${minimum} символов, кроме пробелов.` : '');
    };
    field.addEventListener('input', validate);
    validate();
  }
  form.addEventListener('submit', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    button.textContent = 'Сохраняем…';
  });
  window.addEventListener('pageshow', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = false;
    button.textContent = 'Сохранить заявку ↗';
  });
}
document.querySelector('.error-summary')?.focus();
const copyButton = document.querySelector('#copy-draft');
if (copyButton) {
  copyButton.addEventListener('click', async () => {
    const draft = document.querySelector('#draft');
    const result = document.querySelector('#copy-result');
    try {
      await navigator.clipboard.writeText(draft.value);
      result.textContent = 'Текст скопирован.';
    } catch {
      draft.focus();
      draft.select();
      result.textContent = 'Текст выделен. Нажмите Ctrl+C или выберите «Копировать».';
    }
  });
}
