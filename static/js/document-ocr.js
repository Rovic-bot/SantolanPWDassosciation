/* Optional local OCR: no image uploads, storage, verification or submissions. */
'use strict';
WorkspacePage.run(({on, cleanup}) => {
  document.querySelectorAll('[data-document-ocr]').forEach(panel => {
    const form = panel.parentElement.querySelector('form.registration-editor');
    if (!form || !window.DocumentOCRParser) return;
    const get = key => panel.querySelector(`[data-ocr-${key}]`);
    const say = message => { get('status').textContent = message; };
    let stream, worker, canvas, imageURL, sequence = 0, cameraSequence = 0, busy = false, disposed = false;
    const images = {front: null, back: null};
    let side = 'front';
    let suggestions = [], undo = [];
    panel.hidden = false;
    function syncSides() {
      const receipt = get('kind').value === 'receipt';
      get('sides').hidden = receipt;
      panel.querySelectorAll('[data-ocr-side]').forEach(button => {
        const key = button.dataset.ocrSide, selected = key === side;
        button.setAttribute('aria-pressed', String(selected)); button.disabled = busy;
        const thumb = panel.querySelector(`[data-ocr-thumbnail="${key}"]`);
        thumb.hidden = !images[key];
        if (images[key]) thumb.src = images[key].url; else thumb.removeAttribute('src');
        panel.querySelector(`[data-ocr-side-status="${key}"]`).textContent =
          `${selected ? 'Selected · ' : ''}${images[key] ? 'Image ready' : `Add ${key} image`}`;
      });
      get('upload').textContent = receipt ? 'Choose receipt image' : `Choose ${side} image`;
      get('camera').textContent = receipt ? 'Take receipt photo' : `Take ${side} photo`;
      get('file').setAttribute('aria-label', receipt ? 'Choose receipt image' : `Choose ${side} of ID`);
      get('photo').setAttribute('aria-label', receipt ? 'Photograph receipt' : `Photograph ${side} of ID`);
      get('read').textContent = !receipt && images.front && images.back ? 'Read both sides' : 'Read information';
      get('read').disabled = busy || !Object.values(images).some(Boolean);
      get('preview').hidden = !images[side];
      if (images[side]) get('image').src = images[side].url; else get('image').removeAttribute('src');
    }
    function stopCamera() {
      cameraSequence++;
      stream?.getTracks().forEach(track => track.stop()); stream = null;
      get('video').srcObject = null; get('camera-panel').hidden = true;
    }
    function setBusy(value) {
      busy = value;
      for (const key of ['camera', 'upload', 'phone', 'read', 'rotate', 'remove', 'capture', 'kind', 'apply']) get(key).disabled = value;
      get('progress').hidden = !value;
      panel.setAttribute('aria-busy', String(value));
      syncSides();
    }
    function stopReading() {
      sequence++;
      worker?.terminate(); worker = null;
      setBusy(false);
    }
    function clearImage() {
      if (imageURL) URL.revokeObjectURL(imageURL);
      imageURL = null; canvas = null;
      if (images[side]) images[side].canvas.width = images[side].canvas.height = 0;
      images[side] = null;
      get('image').removeAttribute('src'); get('preview').hidden = true;
      get('file').value = ''; get('photo').value = '';
      syncSides();
    }
    function clearAllImages() {
      const previous = side;
      for (const key of ['front', 'back']) { side = key; clearImage(); }
      side = previous; syncSides();
    }
    function clearResults() {
      get('results').hidden = true; get('fields').replaceChildren(); get('text').textContent = '';
      suggestions = []; undo = []; get('undo').hidden = true;
    }
    function showCanvas() {
      if (imageURL) URL.revokeObjectURL(imageURL);
      images[side] = {canvas, url: canvas.toDataURL('image/jpeg', .9)};
      imageURL = null; get('preview').hidden = false;
      syncSides();
      say(get('kind').value === 'receipt' ? 'Receipt ready. Choose Read information.' :
        `${side === 'front' ? 'Front' : 'Back'} image ready. ${images.front && images.back ? 'Choose Read both sides.' : `Select the ${side === 'front' ? 'back' : 'front'} card to add the other side, or read this image.`}`);
    }
    function resize(source, width, height) {
      const scale = Math.min(1, 2400 / Math.max(width, height));
      const result = document.createElement('canvas');
      result.width = Math.round(width * scale); result.height = Math.round(height * scale);
      const context = result.getContext('2d');
      context.fillStyle = '#fff'; context.fillRect(0, 0, result.width, result.height);
      context.drawImage(source, 0, 0, result.width, result.height);
      return result;
    }
    async function choose(file) {
      if (!file || busy) return;
      stopCamera(); stopReading(); clearResults(); clearImage();
      if (!/^image\/(jpeg|png|webp)$/.test(file.type) || !file.size || file.size > 12 * 1024 * 1024) {
        say('Choose a JPG, PNG or WebP image up to 12 MB. Convert HEIC or PDF to an image first, or enter details manually.'); return;
      }
      const run = sequence;
      const url = URL.createObjectURL(file); imageURL = url;
      try {
        const picture = new Image(); picture.src = url; await picture.decode();
        if (disposed || run !== sequence) return;
        if (!picture.naturalWidth || picture.naturalWidth * picture.naturalHeight > 40000000) throw new Error('size');
        canvas = resize(picture, picture.naturalWidth, picture.naturalHeight); showCanvas();
      } catch {
        if (run === sequence && !disposed) { clearImage(); say('This image could not be read. Try a smaller, clear photo or enter details manually.'); }
      } finally { URL.revokeObjectURL(url); }
    }
    on(get('upload'), 'click', () => get('file').click());
    on(get('phone'), 'click', () => get('photo').click());
    on(get('file'), 'change', () => choose(get('file').files[0]));
    on(get('photo'), 'change', () => choose(get('photo').files[0]));
    panel.querySelectorAll('[data-ocr-side]').forEach(button => on(button, 'click', () => {
      if (busy) return;
      stopCamera(); sequence++;
      if (imageURL) { URL.revokeObjectURL(imageURL); imageURL = null; }
      side = button.dataset.ocrSide; canvas = images[side]?.canvas || null;
      get('file').value = ''; get('photo').value = ''; syncSides();
      say(`${side === 'front' ? 'Front' : 'Back'} selected. Choose an image or use the camera.`);
    }));
    on(get('kind'), 'change', () => {
      stopCamera(); stopReading(); clearResults(); clearAllImages(); side = 'front'; syncSides();
      say('Document type changed. Add the image for this document.');
    });
    on(get('camera'), 'click', async () => {
      stopCamera();
      if (!navigator.mediaDevices?.getUserMedia) { get('phone').hidden = false; get('photo').click(); return; }
      const run = cameraSequence;
      get('camera').disabled = true; say('Allow camera access to photograph the document.');
      try {
        const next = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: 'environment'}, width: {ideal: 1920}, height: {ideal: 1080}}, audio: false});
        if (disposed || run !== cameraSequence) { next.getTracks().forEach(track => track.stop()); return; }
        stream = next; get('video').srcObject = stream; get('camera-panel').hidden = false;
        await get('video').play(); say('Place the document inside the camera view, then capture the photo.');
      } catch {
        if (run === cameraSequence && !disposed) { stopCamera(); get('phone').hidden = false; say('Camera unavailable or permission denied. Choose an image, use your phone camera, or enter the form manually.'); }
      } finally { if (!disposed) get('camera').disabled = busy; }
    });
    on(get('stop'), 'click', () => { stopCamera(); say('Camera closed.'); });
    on(get('capture'), 'click', () => {
      const video = get('video');
      if (!video.videoWidth) { say('The camera is not ready yet. Please try again.'); return; }
      clearResults(); clearImage(); canvas = resize(video, video.videoWidth, video.videoHeight);
      stopCamera(); showCanvas();
    });
    on(get('rotate'), 'click', () => {
      if (!canvas || busy) return;
      const rotated = document.createElement('canvas'); rotated.width = canvas.height; rotated.height = canvas.width;
      const context = rotated.getContext('2d'); context.translate(rotated.width, 0); context.rotate(Math.PI / 2); context.drawImage(canvas, 0, 0);
      canvas = rotated; clearResults(); showCanvas();
    });
    on(get('remove'), 'click', () => { stopReading(); stopCamera(); clearImage(); clearResults(); say(`${side} image removed. You can replace it or read the remaining image.`); });
    on(get('clear'), 'click', () => { stopReading(); stopCamera(); clearAllImages(); clearResults(); say('Scans cleared. Details already entered in the form remain.'); });
    on(get('cancel'), 'click', () => { stopReading(); say('Reading cancelled. You can try again or complete the form manually.'); });
    const allowed = new Set(['first_name', 'middle_name', 'last_name', 'suffix', 'full_name', 'birthdate',
      'house_street', 'address', 'barangay', 'city', 'province', 'region', 'zip_code', 'contact_number', 'email',
      'sex', 'gender', 'civil_status', 'nationality', 'pwd_number', 'date_issued', 'philhealth_number',
      'voter_certification_number', 'sss_number', 'gsis_number', 'psn_number', 'guardian_name', 'guardian_contact',
      'emergency_name', 'emergency_phone', 'blood_type', 'disability_type']);
    function review(result) {
      const text = result.text || '';
      const parsed = result.parsed || window.DocumentOCRParser.extract(text, get('kind').value);
      get('text').textContent = text.slice(0, 30000); get('notes').textContent = parsed.notes.join(' ');
      const values = {...parsed.values};
      if (values.guardian_name && form.elements.namedItem('emergency_name')) {
        values.emergency_name = values.guardian_name; delete values.guardian_name;
      }
      if (values.guardian_contact && form.elements.namedItem('emergency_phone')) {
        values.emergency_phone = values.guardian_contact; delete values.guardian_contact;
      }
      if (values.disability_type && /^physical\s*(?:disability)?\s*(?:\(?ortho(?:pedic)?\)?)?$/i.test(values.disability_type)) {
        values.disability_type = 'Physical / Orthopedic';
      }
      if (values.sex && form.elements.namedItem('gender')) { values.gender = values.sex; delete values.sex; }
      // Let the applicant assign a full, undivided name without losing its text.
      if (values.full_name && !values.first_name && !form.elements.namedItem('full_name')) {
        values.first_name = ''; values.middle_name = ''; values.last_name = '';
        get('notes').textContent += ` Name found: ${values.full_name}. Enter the name parts below before selecting them.`;
      }
      for (const [name, value] of Object.entries(values)) {
        let target = form.elements.namedItem(name), proposed = value;
        if (!target && name === 'disability_type') {
          const label = value === 'Physical / Orthopedic' ? 'Physical Disability' : value;
          target = [...form.querySelectorAll('input[type=checkbox][name=disability_types]')]
            .find(input => input.value.toLowerCase() === label.toLowerCase());
          if (target) proposed = target.value;
        }
        const classification = name === 'disability_type' && target?.type === 'checkbox' && target.name === 'disability_types';
        const property = classification ? 'checked' : 'value';
        if (!allowed.has(name) || !target || !['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName) ||
            target.disabled || target.readOnly || (!classification && ['hidden', 'checkbox', 'radio', 'file'].includes(target.type))) continue;
        if (target.hasAttribute('data-ph-mobile')) {
          proposed = value.replace(/\s/g, '').replace(/^(?:\+63|63|0)(?=9[0-9]{9}$)/, '');
        }
        if (target.tagName === 'SELECT') {
          proposed = [...target.options].find(option => option.value &&
            [option.value, option.textContent].some(label => label.toLowerCase() === value.toLowerCase()))?.value;
          if (!proposed) continue;
        }
        const row = document.createElement('div'); row.className = 'document-ocr-field';
        const label = document.createElement('label'), checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        const sourceName = name === 'emergency_name' ? 'guardian_name' : name === 'emergency_phone' ? 'guardian_contact' : name;
        const uncertain = parsed.uncertain?.includes(sourceName) || (['first_name', 'middle_name', 'last_name'].includes(name) && parsed.uncertain?.includes('full_name'));
        checkbox.checked = !target[property] && Boolean(proposed) && !uncertain;
        const title = target.labels?.[0]?.textContent.replace(/\*\s*(?:\(required\))?/gi, '').replace(/\s+/g, ' ').trim() || name.replaceAll('_', ' ');
        label.append(checkbox, document.createTextNode(title));
        const editor = target.tagName === 'SELECT' ? target.cloneNode(true) : document.createElement('input');
        editor.removeAttribute('name'); editor.removeAttribute('id'); editor.removeAttribute('required');
        editor.removeAttribute('aria-describedby');
        if (target.tagName !== 'SELECT') { editor.type = ['date', 'email'].includes(target.type) ? target.type : 'text'; editor.maxLength = target.maxLength > 0 ? target.maxLength : 1000; }
        editor.className = 'form-control'; editor.value = proposed; editor.setAttribute('aria-label', `Review ${title}`);
        if (classification) editor.readOnly = true;
        if (target.hasAttribute('data-ph-mobile')) editor.pattern = '9[0-9]{9}';
        const current = document.createElement('small'); current.textContent = target[property] ? `Current entry: ${target.value}` : uncertain ? 'Uncertain reading — check the card, then select this detail.' : 'Empty form field';
        row.append(label, editor, current); get('fields').append(row);
        suggestions.push({target, editor, checkbox, current, property, before: target[property]});
      }
      get('results').hidden = false; get('apply').hidden = !suggestions.length;
      say(suggestions.length ? `${result.rotation ? 'Image rotated automatically. ' : ''}Reading complete. Review the suggestions before adding them to the form.` : 'No matching personal fields found. View the extracted text, try a clearer image, or complete the form manually.');
      get('review-heading').focus({preventScroll: true});
    }
    on(get('read'), 'click', async () => {
      const selected = Object.entries(images).filter(([, image]) => image);
      if (!selected.length || busy) return;
      stopCamera(); stopReading(); clearResults(); setBusy(true); const run = sequence;
      const active = () => !disposed && sequence === run;
      get('meter').value = 0; say('Loading the document reader. The first scan may take a little longer.');
      let timer, localWorker, readingSide = '';
      const task = async () => {
        localWorker = new window.DocumentOCRReader({
          workerPath: new URL(panel.dataset.worker, location.href).href,
          corePath: new URL(panel.dataset.core, location.href).href,
          langPath: new URL(panel.dataset.language, location.href).href,
          progress: message => {
            if (active() && message.status === 'checking orientation') say(`Checking image direction (${message.attempt} of 4)…`);
            if (active() && message.status === 'refining address') say('Checking the small address text…');
            if (active() && message.status === 'refining card') say(`Reading faded text on the ${readingSide}…`);
            if (active() && message.status === 'recognizing text') {
              const percent = Math.round(message.progress * 100); get('meter').value = percent;
              say(`Reading ${readingSide} on this device (pass ${message.attempt})… ${percent}%`);
            }
          },
        });
        if (!active()) { localWorker.terminate(); return; }
        worker = localWorker;
        const results = [];
        for (const [key, image] of selected) {
          if (!active()) return;
          readingSide = get('kind').value === 'receipt' ? 'receipt' : `${key} of ID`;
          const kind = get('kind').value === 'pwd' ? `pwd-${key}` : get('kind').value;
          const result = await worker.read(image.canvas, kind);
          if (!active()) return;
          results.push({...result, side: key});
          if (result.rotation) {
            const rotated = window.DocumentOCRReader.rotate(image.canvas, result.rotation);
            image.canvas.width = image.canvas.height = 0;
            images[key] = {canvas: rotated, url: rotated.toDataURL('image/jpeg', .9)};
          }
        }
        if (active()) {
          canvas = images[side]?.canvas || null; syncSides();
          review({text: results.map(result => `${result.side.toUpperCase()}\n${result.text || ''}`).join('\n\n'),
            parsed: window.DocumentOCRParser.merge(results.map(result => result.parsed))});
        }
      };
      try {
        await Promise.race([task(), new Promise((resolve, reject) => { timer = window.setTimeout(() => reject(new Error('timeout')), 90000 * selected.length); })]);
      } catch {
        if (active()) { stopReading(); say('The document reader could not finish. Check your connection, try a smaller image, or enter the details manually.'); }
      } finally {
        window.clearTimeout(timer); localWorker?.terminate();
        if (active()) { worker = null; setBusy(false); }
      }
    });
    on(get('apply'), 'click', () => {
      const applied = []; let skipped = 0;
      for (const item of suggestions) {
        if (!item.checkbox.checked) continue;
        const {target, editor, before, property} = item;
        const value = editor.value.trim();
        if (target[property] !== before || !value || !editor.checkValidity() || target.disabled || target.readOnly ||
            (property === 'checked' && value !== target.value) ||
            (target.dataset.registrationNumber && !(target.dataset.registrationNumber === 'hyphens' ? /^[0-9-]+$/ : /^[0-9]+$/).test(value))) {
          skipped++; item.checkbox.checked = false; item.before = target[property];
          item.current.textContent = `Kept current entry: ${target.value || '(empty)'}`;
          continue;
        }
        target[property] = property === 'checked' ? true : value;
        target.dispatchEvent(new Event('input', {bubbles: true})); target.dispatchEvent(new Event('change', {bubbles: true}));
        if (target[property] !== before) applied.push({target, property, before, after: target[property]});
        item.before = target[property]; item.checkbox.checked = false; item.current.textContent = `Current entry: ${target.value}`;
      }
      if (applied.length) undo = applied;
      get('undo').hidden = !undo.length;
      say(`${applied.length} field${applied.length === 1 ? '' : 's'} added. ${skipped ? `${skipped} changed or invalid field(s) skipped. ` : ''}Check the application below and complete the remaining required fields before submitting.`);
    });
    on(get('undo'), 'click', () => {
      let count = 0;
      for (const item of undo) if (item.target[item.property] === item.after) {
        item.target[item.property] = item.before; item.target.dispatchEvent(new Event('input', {bubbles: true}));
        item.target.dispatchEvent(new Event('change', {bubbles: true})); count++;
      }
      undo = []; get('undo').hidden = true; say(`${count} autofilled fields restored. Any later manual edits were kept.`);
      suggestions.forEach(item => { item.before = item.target[item.property]; item.current.textContent = item.before ? `Current entry: ${item.target.value}` : 'Empty form field'; });
    });
    on(get('continue'), 'click', () => {
      form.scrollIntoView({block: 'start'});
      form.querySelector('input:not([type=hidden]), select, textarea')?.focus({preventScroll: true});
    });
    syncSides();
    on(window, 'pagehide', () => { stopReading(); stopCamera(); clearAllImages(); clearResults(); });
    on(document, 'visibilitychange', () => { if (document.hidden) stopCamera(); });
    cleanup(() => { disposed = true; stopReading(); stopCamera(); clearAllImages(); clearResults(); });
  });
});
