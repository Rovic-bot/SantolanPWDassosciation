/* Render only the displayed receipt fields. Nothing is uploaded or stored. */
(() => {
  'use strict';
  window.ProgramReceiptImage = async (receipt, format) => {
    if (!['png', 'jpeg'].includes(format)) throw new Error('Unsupported image format');
    const reference = receipt.querySelector('#program-receipt-reference').textContent.trim();
    const qr = receipt.querySelector('.program-receipt-qr img');
    if (qr) {
      await qr.decode();
      if (!qr.naturalWidth) throw new Error('QR code unavailable');
    }
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Image saving unavailable');
    const paint = [], width = 1200, left = 40, mainWidth = 660, sideX = 732, sideWidth = 428;
    const ink = '#17191d', muted = '#637083', background = '#f5f5f7', inset = '#f8f9fa';
    const font = (size, weight = 400, family = 'Arial, sans-serif') => `${weight} ${size}px ${family}`;

    function wrap(value, style, maxWidth) {
      ctx.font = style;
      const rows = [];
      for (const paragraph of value.trim().split(/\n/)) {
        let line = '';
        for (const word of paragraph.split(/\s+/)) {
          const candidate = line ? `${line} ${word}` : word;
          if (ctx.measureText(candidate).width <= maxWidth) {line = candidate; continue;}
          if (line) {rows.push(line); line = '';}
          for (const character of word) {
            if (line && ctx.measureText(line + character).width > maxWidth) {rows.push(line); line = '';}
            line += character;
          }
        }
        rows.push(line);
      }
      return rows;
    }
    function text(value, x, y, maxWidth, size, lineHeight, weight = 400, color = muted, family) {
      const style = font(size, weight, family), rows = wrap(value, style, maxWidth);
      paint.push(() => {
        ctx.font = style; ctx.fillStyle = color; ctx.textBaseline = 'top';
        rows.forEach((row, index) => ctx.fillText(row, x, y + index * lineHeight));
      });
      return y + rows.length * lineHeight;
    }
    function rounded(x, y, w, h, color = '#fff', radius = 28) {
      return () => {
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.roundRect(x, y, w, h, radius); ctx.fill();
      };
    }
    function panel(x, y, w, content) {
      const start = paint.length, end = content(y + 28) + 28;
      paint.splice(start, 0, rounded(x, y, w, end - y));
      return end;
    }

    paint.push(() => {
      ctx.strokeStyle = '#08b988'; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.arc(left + 29, 69, 26, -.16, Math.PI * 1.66); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left + 19, 69); ctx.lineTo(left + 28, 78); ctx.lineTo(left + 54, 51); ctx.stroke();
    });
    let y = text(receipt.querySelector('h1').textContent, left, 126, mainWidth, 40, 49, 700, ink);
    y = text(receipt.querySelector('.program-receipt-program').textContent, left, y + 20, mainWidth, 20, 29, 600);
    y = panel(left, y + 36, mainWidth, top => {
      paint.push(rounded(left + 28, top, mainWidth - 56, 84, inset, 18));
      let size = 25;
      while (size > 15) {
        ctx.font = font(size, 700, 'monospace');
        if (ctx.measureText(reference).width <= mainWidth - 104) break;
        size--;
      }
      text(reference, left + 52, top + 28, mainWidth - 104, size, 28, 700, ink, 'monospace');
      return top + 84;
    });
    const change = receipt.querySelector('.program-receipt-change');
    if (change) {
      y = panel(left, y + 24, mainWidth, top => {
        top = text(change.querySelector('h2').textContent, left + 28, top, mainWidth - 56, 22, 29, 700, ink);
        for (const paragraph of change.querySelectorAll('p')) {
          top = text(paragraph.textContent, left + 28, top + 14, mainWidth - 56, 18, 28);
        }
        return top;
      });
    }
    y = panel(left, y + 24, mainWidth, top => {
      top = text(receipt.querySelector('.program-receipt-steps h2').textContent, left + 28, top, mainWidth - 56, 22, 29, 700, ink) + 22;
      const steps = [...receipt.querySelectorAll('.program-receipt-steps li')];
      steps.forEach((step, index) => {
        paint.push(rounded(left + 28, top, 28, 28, background, 14));
        text(String(index + 1), left + 38, top + 5, 18, 15, 18, 700);
        top = text(step.textContent, left + 72, top, mainWidth - 100, 18, 28);
        if (index < steps.length - 1) top += 18;
      });
      return top;
    });
    const sideEnd = panel(sideX, 192, sideWidth, top => {
      paint.push(rounded(sideX + 28, top, 170, 30, background, 15));
      text('AFTER SUBMISSION', sideX + 42, top + 8, 150, 11, 16, 700);
      top = text(receipt.querySelector('#tracking-heading').textContent, sideX + 28, top + 56, sideWidth - 56, 26, 33, 700, ink);
      const summary = receipt.querySelector('.program-receipt-tracking-content > p, .program-receipt-tracking > p:not(.program-receipt-eyebrow)');
      top = text(summary.textContent, sideX + 28, top + 14, sideWidth - 56, 16, 24);
      if (qr) {
        top += 28;
        paint.push(rounded(sideX + 28, top, sideWidth - 56, 272, inset, 18));
        const imageY = top + 16;
        paint.push(() => {
          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(qr, sideX + (sideWidth - 240) / 2, imageY, 240, 240);
        });
        top = text('Scan to open application tracking.', sideX + 28, top + 288, sideWidth - 56, 16, 24, 600);
      }
      const link = receipt.querySelector('.program-receipt-track-button');
      if (link) {
        const url = new URL(link.href);
        top = text(url.origin + url.pathname, sideX + 28, top + 18, sideWidth - 56, 15, 22);
      }
      return top;
    });
    y = Math.max(y, sideEnd) + 28;
    y = text(receipt.querySelector('.program-receipt-guidance p').textContent, left, y, width - 80, 16, 24);
    y = text('Keep this receipt and your application reference private.', left, y + 12, width - 80, 16, 24);
    canvas.width = width * 2;
    canvas.height = Math.ceil(y + 40) * 2;
    ctx.scale(2, 2);
    ctx.fillStyle = background; ctx.fillRect(0, 0, width, canvas.height / 2);
    paint.forEach(draw => draw());
    const type = `image/${format}`;
    const blob = await new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('Image unavailable')), type, .95));
    if (blob.type !== type) throw new Error('Image format unavailable');
    return {blob, filename:`program-receipt-${reference.replace(/[^a-z0-9-]/gi, '-')}.${format}`};
  };
})();
