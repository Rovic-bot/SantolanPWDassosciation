/* Keep title initials visible when a published card image cannot load. */
(() => {
  'use strict';
  const restoreInitials = image => { image.hidden = true; };
  document.addEventListener('error', event => {
    if (event.target.matches?.('img[data-notice-image]')) restoreInitials(event.target);
  }, true);
  const checkImages = () => document.querySelectorAll('img[data-notice-image]').forEach(image => {
    if (image.complete && !image.naturalWidth) restoreInitials(image);
  });
  checkImages();
  document.addEventListener('public:results-updated', checkImages);
})();
