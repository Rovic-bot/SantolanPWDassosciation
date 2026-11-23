/* Fictional two-sided layout; no real person, portrait, seal or signature. */
module.exports = async function pwdFixture(page, side) {
  const data = await page.evaluate(side => {
    const canvas = document.createElement('canvas'); canvas.width = 1200; canvas.height = 800;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#f4f3ec'; ctx.fillRect(0, 0, 1200, 800);
    const text = (value, x, y, size = 24, stamped = false) => {
      ctx.fillStyle = stamped ? '#555' : '#111'; ctx.font = `${stamped ? 'bold' : ''} ${size}px ${stamped ? 'Courier New' : 'Arial'}`;
      ctx.fillText(value, x, y);
    };
    if (side === 'front') {
      text('FICTIONAL TEST CARD - NOT VALID IDENTIFICATION', 80, 42, 22);
      text('PERSONS WITH DISABILITY AFFAIRS OFFICE', 240, 98, 26);
      ctx.fillStyle = '#dce2e5'; ctx.fillRect(900, 160, 250, 350); text('NO PHOTO', 950, 330, 22);
      text('ID NO.', 55, 220); text('00-1234-001-0000042', 180, 210, 33, true);
      text('NAME:', 55, 310); text('JUAN M. DELA CRUZ', 180, 300, 33, true);
      text('PHYSICAL DISABILITY(ORTHO)', 55, 400, 34, true); text('TYPE OF DISABILITY', 270, 440);
      text('08-22-67/56', 55, 540, 34, true); text('01-24-2024', 475, 540, 34, true);
      text('DATE OF BIRTH / AGE', 55, 580); text('DATE OF ISSUE', 485, 580);
      text('08-22-2029', 475, 670, 32, true); text('EXPIRY DATE', 485, 710);
    } else {
      text('ADDRESS:', 45, 120); text('27 TEST STREET Santolan', 210, 110, 33, true);
      text('Pasig City', 210, 195, 33, true); text('SEX:', 760, 195); text('Male', 835, 186, 33, true);
      text('BLOOD TYPE:', 760, 275); text('O+', 950, 265, 33, true);
      text('IN CASE OF EMERGENCY NOTIFY:', 45, 380);
      text('PARENT/GUARDIAN:', 45, 460); text('ANA S. REYES', 330, 450, 33, true);
      text('CONTACT NO:', 45, 540); text('09171234567', 250, 530, 33, true);
      text('FICTIONAL TEST CARD - NOT VALID IDENTIFICATION', 100, 710, 22);
    }
    return canvas.toDataURL('image/png').split(',')[1];
  }, side);
  return {name: `fictional-pwd-${side}.png`, mimeType: 'image/png', buffer: Buffer.from(data, 'base64')};
};
