// Проверка JS-логики без браузера. Узлы страницы заменены маленькими заглушками.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

function element(value = '', minimum = '1') {
  return {
    value, textContent: '', disabled: false, events: {}, listeners: {},
    addEventListener(type, fn) {
      (this.listeners[type] ??= []).push(fn);
      this.events[type] = () => Promise.all(this.listeners[type].map(callback => callback()));
    },
    getAttribute() { return minimum; },
    setCustomValidity(message) { this.validation = message; },
    focus() { this.focused = true; },
    select() { this.selected = true; }
  };
}
const details = element('', '20');
const name = element('', '2');
const button = element();
const form = element();
form.querySelectorAll = () => [name, details];
form.querySelector = () => button;
const nodes = {
  '#details': details, '#counter': element(), '[data-request-form]': form,
  '.error-summary': element(), '#copy-draft': element(),
  '#draft': element('Письмо в архив'), '#copy-result': element()
};
let copied = '';
const navigator = {clipboard: {writeText: async text => {copied = text;}}};
const window = element();
vm.runInNewContext(readFileSync(new URL('../static/app.js', import.meta.url), 'utf8'), {
  document: {querySelector: selector => nodes[selector] || null}, window, navigator
});
assert.equal(nodes['#counter'].textContent, '0/2000');
details.value = 'Достаточно длинное описание для заявки.';
details.events.input();
assert.equal(nodes['#counter'].textContent, `${details.value.length}/2000`);
assert.equal(details.validation, '');
name.value = '   '; name.events.input(); assert.ok(name.validation);
name.value = 'Соколовы'; name.events.input(); assert.equal(name.validation, '');
form.events.submit(); assert.equal(button.disabled, true);
window.events.pageshow(); assert.equal(button.disabled, false);
assert.equal(nodes['.error-summary'].focused, true);
await nodes['#copy-draft'].events.click();
assert.equal(copied, 'Письмо в архив');
assert.equal(nodes['#copy-result'].textContent, 'Текст скопирован.');
navigator.clipboard.writeText = async () => {throw new Error('Permission denied');};
await nodes['#copy-draft'].events.click();
assert.equal(nodes['#draft'].selected, true);
assert.match(nodes['#copy-result'].textContent, /Ctrl\+C/);
console.log('PASS: counter, whitespace, valid input, submit, pageshow, error focus, copy, copy fallback');
