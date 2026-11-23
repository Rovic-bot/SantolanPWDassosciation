/* Small adapter for the pinned Tesseract.js 6.0.1 worker message protocol
 * (upstream src/createWorker.js). Owning the native Worker lets cancellation
 * release it even while the engine or language file is still loading. */
window.DocumentOCRReader = class {
  constructor({workerPath, corePath, langPath, progress}) {
    this.worker = new Worker(workerPath);
    this.pending = new Map(); this.nextId = 0; this.closed = false;
    this.corePath = corePath; this.langPath = langPath;
    this.progress = progress; this.attempt = 1;
    this.worker.onmessage = ({data: message}) => {
      if (this.closed) return;
      if (message.status === 'progress') { progress({...message.data, attempt: this.attempt}); return; }
      const job = this.pending.get(message.jobId);
      if (!job) return;
      this.pending.delete(message.jobId);
      if (message.status === 'resolve') job.resolve(message.data);
      else job.reject(new Error('Document reading failed'));
    };
    this.worker.onerror = event => { event.preventDefault(); this.terminate(); };
    this.worker.onmessageerror = () => this.terminate();
  }
  run(action, payload) {
    if (this.closed) return Promise.reject(new Error('Reader closed'));
    return new Promise((resolve, reject) => {
      const jobId = `ocr-${++this.nextId}`;
      this.pending.set(jobId, {resolve, reject});
      this.worker.postMessage({workerId: 'document-ocr', jobId, action, payload});
    });
  }
  static rotate(canvas, angle, scale = 1) {
    const rotated = document.createElement('canvas');
    const sideways = angle % 180 !== 0;
    rotated.width = Math.round((sideways ? canvas.height : canvas.width) * scale);
    rotated.height = Math.round((sideways ? canvas.width : canvas.height) * scale);
    const context = rotated.getContext('2d');
    context.fillStyle = '#fff'; context.fillRect(0, 0, rotated.width, rotated.height);
    context.translate(rotated.width / 2, rotated.height / 2); context.rotate(angle * Math.PI / 180);
    context.drawImage(canvas, -canvas.width * scale / 2, -canvas.height * scale / 2, canvas.width * scale, canvas.height * scale);
    return rotated;
  }
  static contrast(canvas) {
    // Local thresholding retains faded typewriting even when the surrounding
    // photograph has shadows. The source preview is never changed.
    const context = canvas.getContext('2d'), {width, height} = canvas;
    const pixels = context.getImageData(0, 0, width, height), stride = width + 1;
    const gray = new Uint8Array(width * height), sums = new Uint32Array(stride * (height + 1));
    for (let y = 0; y < height; y++) {
      let row = 0;
      for (let x = 0; x < width; x++) {
        const index = y * width + x, pixel = index * 4;
        gray[index] = Math.round(pixels.data[pixel] * .299 + pixels.data[pixel + 1] * .587 + pixels.data[pixel + 2] * .114);
        row += gray[index]; sums[(y + 1) * stride + x + 1] = sums[y * stride + x + 1] + row;
      }
    }
    const radius = Math.max(15, Math.round(Math.max(width, height) / 90));
    for (let y = 0; y < height; y++) {
      const top = Math.max(0, y - radius), bottom = Math.min(height, y + radius + 1);
      for (let x = 0; x < width; x++) {
        const left = Math.max(0, x - radius), right = Math.min(width, x + radius + 1);
        const mean = (sums[bottom * stride + right] - sums[top * stride + right] - sums[bottom * stride + left] + sums[top * stride + left]) / ((right - left) * (bottom - top));
        const index = y * width + x, value = gray[index] < mean - 9 ? 0 : 255;
        pixels.data[index * 4] = pixels.data[index * 4 + 1] = pixels.data[index * 4 + 2] = value;
      }
    }
    context.putImageData(pixels, 0, 0);
    return canvas;
  }
  async recognize(canvas) {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    canvas.width = canvas.height = 0;
    if (!blob) throw new Error('Image unavailable');
    return this.run('recognize', {image: new Uint8Array(await blob.arrayBuffer()), options: {}, output: {text: true, blocks: true}});
  }
  static clarify(canvas) {
    const context = canvas.getContext('2d'), pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const histogram = new Uint32Array(256); let count = 0;
    for (let index = 0; index < pixels.data.length; index += 4) {
      const value = Math.round((pixels.data[index] + pixels.data[index + 1] + pixels.data[index + 2]) / 3);
      if (value < 248) { histogram[value]++; count++; }
    }
    let sum = 0, low = 0, high = 255;
    for (let value = 0; value < 256; value++) { sum += histogram[value]; if (sum < count * .03) low = value; if (sum < count * .9) high = value; }
    for (let index = 0; index < pixels.data.length; index += 4) {
      const gray = (pixels.data[index] + pixels.data[index + 1] + pixels.data[index + 2]) / 3;
      const value = Math.max(0, Math.min(255, (gray - low) * 255 / Math.max(20, high - low)));
      pixels.data[index] = pixels.data[index + 1] = pixels.data[index + 2] = value;
    }
    // Printed rules otherwise dominate the threshold for faint handwriting.
    // Remove only long rules near the edges of the isolated value region.
    for (let y = 0; y < canvas.height; y++) {
      if (y > canvas.height * .3 && y < canvas.height * .65) continue;
      let dark = 0;
      for (let x = 0; x < canvas.width; x++) if (pixels.data[(y * canvas.width + x) * 4] < 100) dark++;
      if (dark < canvas.width * .5) continue;
      const start = y < canvas.height * .3 ? 0 : Math.max(0, y - 2);
      const end = y < canvas.height * .3 ? Math.min(canvas.height, y + 3) : canvas.height;
      for (let row = start; row < end; row++) for (let x = 0; x < canvas.width; x++) {
        const index = (row * canvas.width + x) * 4;
        pixels.data[index] = pixels.data[index + 1] = pixels.data[index + 2] = 255;
      }
    }
    context.putImageData(pixels, 0, 0); return canvas;
  }
  async read(canvas, kind = 'id') {
    if (!this.ready) {
      await this.run('load', {options: {lstmOnly: true, corePath: this.corePath, logging: false}});
      await this.run('loadLanguage', {langs: 'eng', options: {langPath: this.langPath, cacheMethod: 'none', gzip: true, lstmOnly: true}});
      await this.run('initialize', {langs: 'eng', oem: 1, config: {}});
      this.ready = true;
    }
    await this.run('setParameters', {params: {tessedit_pageseg_mode: kind === 'receipt' ? '6' : '11', preserve_interword_spaces: '1'}});
    let best;
    const scale = Math.min(2, 3400 / Math.max(canvas.width, canvas.height));
    for (const [index, rotation] of [0, 270, 90, 180].entries()) {
      if (this.closed) throw new Error('Reader stopped');
      this.attempt = index + 1;
      this.progress({status: 'checking orientation', attempt: this.attempt});
      const prepared = this.constructor.rotate(canvas, rotation, scale);
      const blob = await new Promise(resolve => prepared.toBlob(resolve, 'image/png'));
      prepared.width = prepared.height = 0;
      if (!blob) throw new Error('Image unavailable');
      const image = new Uint8Array(await blob.arrayBuffer());
      const result = await this.run('recognize', {image, options: {}, output: {text: true, blocks: true}});
      const parsed = window.DocumentOCRParser.fromResult(result, kind);
      const score = window.DocumentOCRParser.quality(parsed, result.confidence);
      if (!best || score > best.score) best = {...result, parsed, score, rotation};
      // A clearly readable upright card needs no additional passes. A receipt
      // can contain fewer personal fields, so two labelled values suffice.
      if ((parsed.values.first_name && parsed.values.last_name && parsed.values.birthdate) ||
          (kind.startsWith('pwd') && parsed.matchedLabels >= 2) ||
          (kind === 'receipt' && parsed.matchedLabels >= 2 && Object.keys(parsed.values).length >= 2)) break;
    }
    if (kind.startsWith('pwd') && !this.closed) {
      const original = best;
      this.progress({status: 'refining card', attempt: ++this.attempt});
      const prepared = this.constructor.contrast(this.constructor.rotate(canvas, best.rotation, scale));
      const refined = await this.recognize(prepared);
      const parsed = window.DocumentOCRParser.fromResult(refined, kind);
      const score = window.DocumentOCRParser.quality(parsed, refined.confidence);
      if (score > best.score) best = {...refined, parsed, score, rotation: best.rotation};
      const source = this.constructor.rotate(canvas, best.rotation, scale);
      const regions = window.DocumentOCRParser.pwdRegions([original, refined], kind, source.width, source.height);
      const completeName = best.parsed.values.first_name && best.parsed.values.last_name;
      const fieldText = [], uncertain = [];
      await this.run('setParameters', {params: {tessedit_pageseg_mode: '7', thresholding_method: '0'}});
      for (const region of regions) {
        if (this.closed) throw new Error('Reader stopped');
        if ((region.key === 'full_name' && completeName) ||
            (['birthdate', 'date_issued', 'sex', 'guardian_contact', 'blood_type'].includes(region.key) && best.parsed.values[region.key])) continue;
        const crop = document.createElement('canvas'), w = region.x1 - region.x0, h = region.y1 - region.y0;
        crop.width = w + 40; crop.height = h + 40;
        const context = crop.getContext('2d'); context.fillStyle = '#fff'; context.fillRect(0, 0, crop.width, crop.height);
        context.translate(crop.width / 2, crop.height / 2); context.rotate(-region.angle * Math.PI / 180);
        context.drawImage(source, region.x0, region.y0, w, h, -w / 2, -h / 2, w, h);
        await this.run('setParameters', {params: {tessedit_char_whitelist:
          ['pwd_number', 'birthdate', 'date_issued', 'guardian_contact'].includes(region.key) ? '0123456789-./ ' : ''}});
        const reading = await this.recognize(this.constructor.clarify(crop));
        const value = (reading.text || '').trim().replace(/^[|_:.,\s-]+|[|_\s]+$/g, '');
        const faintNumber = region.key === 'pwd_number' && reading.confidence >= 20 && /^\d{2}-\d{4}-\d{3}-\d{7}$/.test(value.replace(/\s/g, ''));
        if (value && (reading.confidence >= 35 || faintNumber)) {
          fieldText.push([region.key, value]);
          if (reading.confidence < 70) uncertain.push(region.key);
        }
      }
      source.width = source.height = 0;
      const names = {pwd_number:'PWD No',full_name:'Name',birthdate:'Date of birth / age',date_issued:'Date of issue',
        disability_type:'Type of disability',address:'Address',sex:'Sex',guardian_name:'Parent/guardian',guardian_contact:'Guardian contact number',blood_type:'Blood type'};
      const city = fieldText.find(([key]) => key === 'city_line')?.[1] || best.parsed.values.city;
      const text = fieldText.map(([key, value]) => key === 'sex_line' ? value : names[key] ?
        `${names[key]}: ${value}${key === 'address' && city && /city\b/i.test(city) ? `, ${city}` : ''}` : '').filter(Boolean).join('\n');
      const closeup = window.DocumentOCRParser.extract(text, kind);
      // Field close-ups isolate faint values from dark captions and ruling.
      // Keep the full scan as the fallback for fields a close-up cannot read.
      best.parsed.values = {...best.parsed.values, ...closeup.values};
      best.parsed.uncertain = uncertain;
      best.parsed.notes = [...new Set([...best.parsed.notes, ...closeup.notes, 'Check faded or handwritten text carefully against the card.'])];
      best.text += `\n\nField close-ups:\n${text}`;
      await this.run('setParameters', {params: {thresholding_method: '0', tessedit_char_whitelist: ''}});
    }
    // The compact National ID address sits over a security pattern. Re-read
    // its detected text region separately, excluding portrait/QR/UI graphics.
    const address = best.parsed.regions?.address;
    if (best.parsed.nationalId && address && !this.closed) {
      this.progress({status: 'refining address', attempt: this.attempt});
      const prepared = this.constructor.rotate(canvas, best.rotation, scale);
      const left = Math.max(0, address.x0 - 20), top = Math.max(0, address.y0 - 15);
      const crop = document.createElement('canvas');
      crop.width = Math.min(prepared.width, address.x1 + 20) - left;
      crop.height = Math.min(prepared.height, address.y1 + 20) - top;
      const context = crop.getContext('2d');
      context.drawImage(prepared, left, top, crop.width, crop.height, 0, 0, crop.width, crop.height);
      // Suppress the pale coloured security background in this text-only crop.
      // The original image/result remain available if the refinement is weak.
      const pixels = context.getImageData(0, 0, crop.width, crop.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const value = Math.max(pixels.data[index], pixels.data[index + 1], pixels.data[index + 2]) > 160 ? 255 : 0;
        pixels.data[index] = pixels.data[index + 1] = pixels.data[index + 2] = value;
      }
      context.putImageData(pixels, 0, 0);
      prepared.width = prepared.height = 0;
      const blob = await new Promise(resolve => crop.toBlob(resolve, 'image/png'));
      crop.width = crop.height = 0;
      if (blob) {
        await this.run('setParameters', {params: {tessedit_pageseg_mode: '6'}});
        const refined = await this.run('recognize', {image: new Uint8Array(await blob.arrayBuffer()), options: {}, output: {text: true, blocks: true}});
        const parsed = window.DocumentOCRParser.fromResult(refined, kind, true);
        if (refined.confidence >= 70 && parsed.values.address && parsed.values.house_street) {
          for (const field of ['address', 'house_street', 'barangay', 'city', 'province', 'region', 'zip_code']) {
            if (parsed.values[field]) best.parsed.values[field] = parsed.values[field];
          }
          best.text += `\n\nAddress close-up:\n${refined.text}`;
        }
      }
    }
    return best;
  }
  terminate() {
    if (this.closed) return;
    this.closed = true; this.worker.terminate();
    this.pending.forEach(job => job.reject(new Error('Reader stopped')));
    this.pending.clear();
  }
};
