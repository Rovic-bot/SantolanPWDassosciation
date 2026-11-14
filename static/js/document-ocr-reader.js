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
  async read(canvas, kind = 'id') {
    await this.run('load', {options: {lstmOnly: true, corePath: this.corePath, logging: false}});
    await this.run('loadLanguage', {langs: 'eng', options: {langPath: this.langPath, cacheMethod: 'none', gzip: true, lstmOnly: true}});
    await this.run('initialize', {langs: 'eng', oem: 1, config: {}});
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
          (kind === 'receipt' && parsed.matchedLabels >= 2 && Object.keys(parsed.values).length >= 2)) break;
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
