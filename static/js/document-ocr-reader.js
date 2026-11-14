/* Small adapter for the pinned Tesseract.js 6.0.1 worker message protocol
 * (upstream src/createWorker.js). Owning the native Worker lets cancellation
 * release it even while the engine or language file is still loading. */
window.DocumentOCRReader = class {
  constructor({workerPath, corePath, langPath, progress}) {
    this.worker = new Worker(workerPath);
    this.pending = new Map(); this.nextId = 0; this.closed = false;
    this.corePath = corePath; this.langPath = langPath;
    this.worker.onmessage = ({data: message}) => {
      if (this.closed) return;
      if (message.status === 'progress') { progress(message.data); return; }
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
  async read(canvas) {
    await this.run('load', {options: {lstmOnly: true, corePath: this.corePath, logging: false}});
    await this.run('loadLanguage', {langs: 'eng', options: {langPath: this.langPath, cacheMethod: 'none', gzip: true, lstmOnly: true}});
    await this.run('initialize', {langs: 'eng', oem: 1, config: {}});
    await this.run('setParameters', {params: {tessedit_pageseg_mode: '6', preserve_interword_spaces: '1'}});
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Image unavailable');
    const image = new Uint8Array(await blob.arrayBuffer());
    return this.run('recognize', {image, options: {}, output: {text: true}});
  }
  terminate() {
    if (this.closed) return;
    this.closed = true; this.worker.terminate();
    this.pending.forEach(job => job.reject(new Error('Reader stopped')));
    this.pending.clear();
  }
};
