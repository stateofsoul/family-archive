const details = document.querySelector('#details');

if (details) {
  const counter = document.querySelector('#counter');

  const updateCounter = () => {
    counter.textContent = `${details.value.length}/2000`;
  };

  details.addEventListener('input', updateCounter);
  updateCounter();
}

const form = document.querySelector('[data-request-form]');

if (form) {
  for (const field of form.querySelectorAll('[required]')) {
    const validate = () => {
      const minimum = Number(field.getAttribute('minlength')) || 1;
      const tooShort = field.value.trim().length < minimum;

      field.setCustomValidity(
        tooShort ? `Введите не меньше ${minimum} символов, без пробелов по краям.` : ''
      );
    };

    field.addEventListener('input', validate);
    validate();
  }

  form.addEventListener('submit', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    button.textContent = 'Сохраняем...';
  });

  window.addEventListener('pageshow', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = false;
    button.textContent = 'Сохранить заявку';
  });
}

const errorSummary = document.querySelector('.error-summary');
if (errorSummary) {
  errorSummary.focus();
}

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
      result.textContent = 'Текст выделен. Скопируйте его вручную: Ctrl+C или ⌘C.';
    }
  });
}
