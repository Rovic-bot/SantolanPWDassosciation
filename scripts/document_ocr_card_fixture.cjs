/* Fictional test artwork only. Contains no real identity, signature or QR data. */
module.exports = async function cardFixture(page, angle = 90) {
  const data = await page.evaluate(angle => {
    const card=document.createElement('canvas');card.width=960;card.height=600;
    const ctx=card.getContext('2d');ctx.fillStyle='#f8faf3';ctx.fillRect(0,0,960,600);
    ctx.strokeStyle='#dfede8';ctx.lineWidth=1;
    for(let i=0;i<1000;i+=8){ctx.beginPath();ctx.moveTo(i,0);ctx.bezierCurveTo(i-70,210,i+70,410,i,600);ctx.stroke();}
    ctx.fillStyle='#111';ctx.font='bold 24px Arial';ctx.fillText('FICTIONAL OCR TEST CARD',245,46);
    ctx.font='18px Arial';ctx.fillText('Philippine National ID layout test',245,75);
    ctx.fillStyle='#d2dde1';ctx.fillRect(50,120,225,260);
    ctx.fillStyle='#405565';ctx.font='18px Arial';ctx.fillText('PHOTO PLACEHOLDER',64,240);
    ctx.font='15px Arial';ctx.fillText('NOT VALID IDENTIFICATION',54,405);
    ctx.fillStyle='#111';
    const fields=[['APELYIDO/LAST NAME','REYES'],['MGA PANGALAN/GIVEN NAMES','ANA MARIA'],
      ['GITNANG APELYIDO/MIDDLE NAME','SANTOS'],['PETSA NG KAPANGANAKAN/DATE OF BIRTH','May 14, 1988']];
    fields.forEach(([label,value],i)=>{ctx.font='12px Arial';ctx.fillText(label,330,135+i*75);ctx.font='bold 21px Arial';ctx.fillText(value,330,161+i*75);});
    // Geometric pattern deliberately cannot be used as a government QR code.
    for(let y=0;y<15;y++)for(let x=0;x<15;x++)if((x*7+y*11)%4<2)ctx.fillRect(750+x*10,150+y*10,10,10);
    ctx.font='12px Arial';ctx.fillText('TEST PATTERN',765,325);
    ctx.font='13px Arial';ctx.fillText('TIRAHAN/ADDRESS',50,465);
    ctx.font='bold 18px Arial';ctx.fillText('88 EXAMPLE STREET, DEMO BARANGAY, CITY OF EXAMPLE, NCR,',50,495);
    ctx.fillText('SECOND DISTRICT, PHILIPPINES, 1234',50,524);
    const turned=document.createElement('canvas');turned.width=angle%180?600:960;turned.height=angle%180?960:600;
    const t=turned.getContext('2d');t.translate(turned.width/2,turned.height/2);t.rotate(angle*Math.PI/180);t.drawImage(card,-480,-300);
    const screenshot=document.createElement('canvas');screenshot.width=720;screenshot.height=1400;
    const s=screenshot.getContext('2d');s.fillStyle='#666';s.fillRect(0,0,720,1400);s.fillStyle='#fff';s.fillRect(18,70,684,1210);
    const scale=Math.min(640/turned.width,980/turned.height);
    s.drawImage(turned,(720-turned.width*scale)/2,115,turned.width*scale,turned.height*scale);
    s.fillStyle='#17496f';s.font='18px Arial';s.fillText('Show back ID',110,1150);s.fillText('Enlarge QR',430,1150);s.fillText('Close',330,1230);
    return screenshot.toDataURL('image/png').split(',')[1];
  },angle);
  return {name:'fictional-national-id-layout.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')};
};
