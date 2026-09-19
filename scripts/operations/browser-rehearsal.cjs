const { chromium, request } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const base = process.env.AUDIT_BROWSER_URL || 'https://localhost:58443';
const mailbox = process.env.AUDIT_MAILBOX;
const password = 'Synthetic-audit-password-184!';
function otp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = [...secret.replace(/=+$/, '')].map(c=>alphabet.indexOf(c).toString(2).padStart(5,'0')).join('');
  const bytes = Buffer.from(bits.match(/.{8}/g).map(x=>parseInt(x,2)));
  const counter=Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));
  const digest=crypto.createHmac('sha1',bytes).update(counter).digest(); const off=digest[19]&15;
  return String(digest.readUInt32BE(off)&0x7fffffff).slice(0) % 1000000 + '';
}
(async()=>{
  const checks=[]; const api=await request.newContext({baseURL:base,ignoreHTTPSErrors:true});
  const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true});
  try {
    const anonymous=await api.get('/api/me/usage'); assert.equal(anonymous.status(),401);
    const mail=`browser-${Date.now()}@example.com`;
    assert.equal((await api.post('/api/auth/register',{data:{email:mail,name:'Synthetic browser',password}})).status(),201);
    assert.equal((await api.post('/api/auth/login',{data:{email:mail,password}})).status(),403);
    async function tokenFor(marker) {
      for(let n=0;n<40;n++) {
        for(const file of await fs.readdir(mailbox)) {
          const message=JSON.parse(await fs.readFile(`${mailbox}/${file}`,'utf8'));
          if(message.to===mail && message.body.includes(marker)) return new URL(message.body.match(/https:\/\/[^\s]+/)[0]).hash.split('token=')[1];
        }
        await new Promise(r=>setTimeout(r,100));
      }
      throw Error('Synthetic email not received');
    }
    const verification=await tokenFor('verify-email');
    assert.equal((await api.post('/api/auth/verify-email',{data:{token:verification}})).status(),200);
    assert.equal((await api.post('/api/auth/verify-email',{data:{token:verification}})).status(),400);
    const login=await api.post('/api/auth/login',{data:{email:mail,password}}); assert.equal(login.status(),200);
    const oldToken=(await login.json()).access_token;
    const headers={Authorization:`Bearer ${oldToken}`};
    const account=await api.get('/api/me/subscription',{headers});assert.equal(account.status(),200);
    assert.equal(account.headers()['cache-control'],'no-store');
    assert.equal((await api.get('/api/ai/providers',{headers})).status(),403);
    const page=await browser.newPage({ignoreHTTPSErrors:true,viewport:{width:1280,height:900}});
    await page.addInitScript(t=>sessionStorage.setItem('smart-exam-token',t),oldToken);
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`${base}/#/account`);
    try { await page.getByRole('region',{name:'Gói sử dụng',exact:true}).waitFor(); }
    catch { throw Error(JSON.stringify({stage:'teacher-account',url:page.url(),errors,headings:await page.locator('h1,h2').allTextContents(),body:(await page.locator('body').innerText()).slice(0,1200)})); }
    await page.goto(`${base}/#/documents`);
    await page.getByLabel('Thông tin xử lý dữ liệu').waitFor();
    for(const width of [390,768,1280]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    }
    await page.close(); assert.deepEqual(errors,[]); checks.push('teacher browser account/documents and responsive data notice');
    assert.equal((await api.post('/api/auth/forgot-password',{data:{email:mail}})).status(),200);
    const reset=await tokenFor('reset-password');
    const nextPassword='Synthetic-new-password-184!';
    assert.equal((await api.post('/api/auth/reset-password',{data:{token:reset,new_password:nextPassword}})).status(),200);
    assert.equal((await api.get('/api/auth/me',{headers})).status(),401);
    assert.equal((await api.post('/api/auth/login',{data:{email:mail,password}})).status(),401);
    const nextLogin=await api.post('/api/auth/login',{data:{email:mail,password:nextPassword}});assert.equal(nextLogin.status(),200);
    const nextHeaders={Authorization:`Bearer ${(await nextLogin.json()).access_token}`};
    assert.equal((await api.post('/api/auth/logout',{headers:nextHeaders})).status(),204);
    assert.equal((await api.get('/api/auth/me',{headers:nextHeaders})).status(),401);
    checks.push('SMTP register/verify/reset; token one-use; password rotation and logout revoke old JWT');
    const rootLogin=await api.post('/api/auth/login',{data:{email:'operator@example.com',password}});assert.equal(rootLogin.status(),200);
    const rootToken=(await rootLogin.json()).access_token;
    const rootHeaders={Authorization:`Bearer ${rootToken}`};
    assert.equal((await api.get('/api/usage/report',{headers:rootHeaders})).status(),403);
    const root=await browser.newPage({ignoreHTTPSErrors:true});
    const rootResponses=[];root.on('response', r=>{if(new URL(r.url()).pathname.startsWith('/api/'))rootResponses.push({path:new URL(r.url()).pathname,status:r.status()});});
    await root.addInitScript(t=>sessionStorage.setItem('smart-exam-token',t),rootToken);
    await root.goto(`${base}/#/account`);
    const panel=root.getByRole('region',{name:'Xác thực MFA quản trị'});
    await panel.getByLabel('Mật khẩu hiện tại').fill(password);
    const setupEvents=[];
    root.on('requestfailed', r=>setupEvents.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));
    let setup;
    try {
      const [response]=await Promise.all([root.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/mfa/setup'), panel.getByRole('button',{name:'Thiết lập lần đầu'}).click()]);
      assert.equal(response.status(),200,'MFA setup response');setup=await response.json();
    } catch(error) { throw Error(JSON.stringify({stage:'mfa-setup',message:error.message,events:setupEvents,alerts:await root.getByRole('alert').allTextContents(),responses:rootResponses,url:root.url(),headings:await root.locator('h1,h2').allTextContents()})); }
    await panel.getByLabel('Mã xác thực hoặc mã khôi phục').fill(otp(setup.secret).padStart(6,'0'));
    const [verificationResponse]=await Promise.all([root.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/mfa/verify'), panel.getByRole('button',{name:'Xác thực MFA',exact:true}).click()]);
    const elevated=await verificationResponse.json(); assert.ok(elevated.access_token);
    const elevatedHeaders={Authorization:`Bearer ${elevated.access_token}`};
    assert.equal((await api.get('/api/usage/report',{headers:elevatedHeaders})).status(),200);
    const recovery=elevated.recovery_codes[0];
    assert.equal((await api.post('/api/auth/mfa/verify',{headers:rootHeaders,data:{password,code:recovery}})).status(),200);
    assert.equal((await api.post('/api/auth/mfa/verify',{headers:rootHeaders,data:{password,code:recovery}})).status(),400);
    await root.close();checks.push('MFA browser enrollment and direct API bypass/recovery replay rejection');
    console.log(JSON.stringify({passed:true,checks,scope:'Local TLS proxy and synthetic SMTP; no external provider or mail delivery'},null,2));
  } finally {await browser.close();await api.dispose();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
