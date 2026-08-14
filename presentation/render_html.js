const puppeteer=require('puppeteer-core');
const path=require('path');
const BASE='UGENCE_SERVICENOW_ARCHITECTURE_AND_USE_CASE_BRIEFING';
(async()=>{
  const browser=await puppeteer.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox','--disable-gpu','--force-color-profile=srgb'],headless:'new'});
  const page=await browser.newPage();
  await page.setViewport({width:1280,height:720,deviceScaleFactor:1.5});
  await page.goto('file://'+path.resolve(BASE+'.render.html'),{waitUntil:'networkidle0'});
  await page.pdf({path:BASE+'.pdf',preferCSSPageSize:true,printBackground:true});
  const boxes=await page.$$('.page');
  for(let i=0;i<boxes.length;i++){ const bb=await boxes[i].boundingBox();
    await page.screenshot({path:`pslide-${String(i+1).padStart(2,'0')}.png`,clip:{x:bb.x,y:bb.y,width:1280,height:720}});
  }
  console.log('rendered',boxes.length,'slides + pdf');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
