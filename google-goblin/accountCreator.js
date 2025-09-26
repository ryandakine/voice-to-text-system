const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const RecaptchaPlugin = require('puppeteer-extra-plugin-recaptcha');
const proxyChain = require('proxy-chain');
const Solver = require('2captcha');
const SMSActivate = require('sms-activate');
const CryptoJS = require('crypto-js');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());
puppeteer.use(RecaptchaPlugin({
  provider: { id: '2captcha', token: 'YOUR_2CAPTCHA_API_KEY' },
  visualFeedback: true
}));

// JSON file storage instead of SQLite
const accountsFile = path.join(__dirname, 'accounts.json');
const historyFile = path.join(__dirname, 'history.json');

// Initialize JSON files if they don't exist
if (!fs.existsSync(accountsFile)) {
  fs.writeFileSync(accountsFile, JSON.stringify([]));
}
if (!fs.existsSync(historyFile)) {
  fs.writeFileSync(historyFile, JSON.stringify([]));
}

const smsClient = new SMSActivate('YOUR_SMS_ACTIVATE_API_KEY');
const encryptionKey = 'FuckGoogle2025'; // Change this

function encrypt(text) {
  return CryptoJS.AES.encrypt(text, encryptionKey).toString();
}

function decrypt(ciphertext) {
  const bytes = CryptoJS.AES.decrypt(ciphertext, encryptionKey);
  return bytes.toString(CryptoJS.enc.Utf8);
}

function log(message) {
  const encryptedMsg = encrypt(message);
  fs.appendFileSync('goblin_log.txt', `${new Date().toISOString()} - ${encryptedMsg}\n`);
}

module.exports = {
  async createAccount(data, progressCallback) {
    for (let attempt = 1; attempt <= 3; attempt++) {
      let browser = null;
      let proxyUrl = null;
      
      try {
        progressCallback(10, 'Setting up proxy...');
        if (data.proxyDepth > 0) {
          proxyUrl = await this.setupProxy(data.proxyDepth);
        }
        
        progressCallback(20, 'Launching browser...');
        browser = await puppeteer.launch({
          headless: data.headless, // Use toggle
          args: proxyUrl ? [`--proxy-server=${proxyUrl}`] : []
        });
        
        const page = await browser.newPage();
        
        progressCallback(30, 'Navigating to signup...');
        await page.goto('https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp');
        
        await page.type('[name=firstName]', data.name.split(' ')[0]);
        await page.type('[name=lastName]', data.name.split(' ')[1] || '');
        await page.type('[name=Username]', generateUsername(data.name));
        
        const pw = generatePassword();
        await page.type('[name=Passwd]', pw);
        await page.type('[name=ConfirmPasswd]', pw);
        await page.click('button[type=button]');
        await page.waitForNavigation();
        
        progressCallback(50, 'Handling verification...');
        if (data.autoBuyNumber) {
          const number = await smsClient.getNumber({ service: 'go' });
          await page.type('[name=phoneNumber]', number.phone);
          await page.click('button[type=button]');
          
          const code = await this.waitForSMS(number.id);
          await page.type('[name=code]', code);
          await page.click('button[type=button]');
        }
        
        await page.type('[name=recoveryEmail]', data.tempEmail);
        await page.click('button[type=button]');
        
        await page.select('[name=month]', (Math.floor(Math.random() * 12) + 1).toString());
        await page.type('[name=day]', (Math.floor(Math.random() * 28) + 1).toString());
        await page.type('[name=year]', data.birthYear.toString());
        await page.select('[name=gender]', (Math.floor(Math.random() * 3) + 1).toString());
        await page.click('button[type=button]');
        
        progressCallback(70, 'Solving CAPTCHA if needed...');
        if (await page.$('g-recaptcha')) {
          const { captchas } = await page.solveRecaptchas();
          if (captchas[0].solved) log('CAPTCHA solved');
        }
        
        await page.click('button[type=button]'); // Agree terms
        
        const username = await page.evaluate(() => document.querySelector('[name=Username]').value);
        
        progressCallback(90, 'Saving to DB...');
        const accounts = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
        const newAccount = {
          id: accounts.length + 1,
          username,
          password: encrypt(pw),
          name: data.name,
          birthYear: data.birthYear,
          birthplace: data.birthplace,
          createdAt: new Date().toISOString()
        };
        accounts.push(newAccount);
        fs.writeFileSync(accountsFile, JSON.stringify(accounts, null, 2));
        
        const history = JSON.parse(fs.readFileSync(historyFile, 'utf8'));
        history.push({
          id: history.length + 1,
          status: 'success',
          timestamp: new Date().toISOString()
        });
        fs.writeFileSync(historyFile, JSON.stringify(history, null, 2));
        
        await new Promise(r => setTimeout(r, Math.random() * 10000 + 5000)); // Random delay
        
        return { username, password: pw };
        
      } catch (err) {
        log(`Attempt ${attempt} failed: ${err.message}`);
        const history = JSON.parse(fs.readFileSync(historyFile, 'utf8'));
        history.push({
          id: history.length + 1,
          status: 'failure',
          error: err.message,
          timestamp: new Date().toISOString()
        });
        fs.writeFileSync(historyFile, JSON.stringify(history, null, 2));
        if (attempt === 3) throw err;
      } finally {
        if (browser) await browser.close();
        if (proxyUrl) await proxyChain.closeAnonymizedProxy(proxyUrl, true);
      }
    }
  },

  async setupProxy(depth) {
    const proxies = [
      'http://20.27.14.220:8561',
      'http://47.252.29.28:11222',
      'http://66.36.234.130:1339',
      'http://5.78.130.46:12016',
      'http://200.174.198.158:8888',
      'http://8.209.255.114:20172',
      'http://4.245.123.244:80',
      'http://4.195.16.140:80',
      'http://65.108.251.40:38328',
      'http://129.159.114.120:8080'
    ];
    
    let anonymized = proxies[0];
    for (let i = 1; i < depth && i < proxies.length; i++) {
      if (!await this.testProxy(proxies[i])) continue; // Skip dead
      anonymized = await proxyChain.anonymizeProxy(anonymized + ' -> ' + proxies[i]);
    }
    return anonymized;
  },

  async testProxy(proxy) {
    try {
      const response = await fetch('https://www.google.com', { proxy });
      return response.ok;
    } catch {
      return false;
    }
  },

  async waitForSMS(id) {
    for (let i = 0; i < 12; i++) {
      const status = await smsClient.getStatus(id);
      if (status.code) return status.code;
      await new Promise(r => setTimeout(r, 5000));
    }
    throw new Error('No SMS received');
  },

  getHistory() {
    const accounts = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
    return accounts.map(account => ({ ...account, password: decrypt(account.password) }));
  },

  exportHistory() {
    const accounts = this.getHistory();
    let csv = 'ID,Username,Password,Name,BirthYear,Birthplace,CreatedAt\n';
    accounts.forEach(account => csv += `${account.id},${account.username},${account.password},${account.name},${account.birthYear},${account.birthplace},${account.createdAt}\n`);
    fs.writeFileSync('export.csv', csv);
    return 'export.csv';
  },

  nukeData() {
    if (fs.existsSync(accountsFile)) fs.unlinkSync(accountsFile);
    if (fs.existsSync(historyFile)) fs.unlinkSync(historyFile);
    if (fs.existsSync('goblin_log.txt')) fs.unlinkSync('goblin_log.txt');
    return true;
  }
};

function generateUsername(name) {
  const base = name.toLowerCase().replace(/\s/g, '');
  return base + Math.floor(Math.random() * 10000);
}

function generatePassword() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()';
  let pw = '';
  for (let i = 0; i < 16; i++) {
    pw += chars[Math.floor(Math.random() * chars.length)];
  }
  return pw;
}