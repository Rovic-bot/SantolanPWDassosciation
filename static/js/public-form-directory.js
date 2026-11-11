// The directory remains a native, keyboard-operable disclosure without JavaScript.
const residentDirectory = document.querySelector('[data-form-directory]');
if (residentDirectory) {
  residentDirectory.open = window.matchMedia('(min-width: 901px)').matches;
}
