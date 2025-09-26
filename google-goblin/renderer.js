// renderer.js
const Mailjs = require('@cemalgnlts/mailjs');

// DOM Elements
const spawnButton = document.getElementById('spawnButton');
const accountForm = document.getElementById('accountForm');
const randomizeButton = document.getElementById('randomizeButton');
const createButton = document.getElementById('createButton');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressMsg = document.getElementById('progressMsg');
const emailSection = document.getElementById('emailSection');
const emailInbox = document.getElementById('emailInbox');
const resultSection = document.getElementById('resultSection');
const successCard = document.getElementById('successCard');
const failureCard = document.getElementById('failureCard');
const successUsername = document.getElementById('successUsername');
const successPassword = document.getElementById('successPassword');
const copyCredsButton = document.getElementById('copyCredsButton');
const exportSingleButton = document.getElementById('exportSingleButton');
const retryButton = document.getElementById('retryButton');
const cryButton = document.getElementById('cryButton');
const proxySlider = document.getElementById('proxySlider');
const proxyValue = document.getElementById('proxyValue');
const numberToggle = document.getElementById('numberToggle');
const headlessToggle = document.getElementById('headlessToggle');
const nukeButton = document.getElementById('nukeButton');
const historySection = document.getElementById('historySection');
const historyCards = document.getElementById('historyCards');
const exportAllButton = document.getElementById('exportAllButton');

// State
let currentAccount = null;
let tempEmail = null;
let mailClient = null;
let accountHistory = [];
let pollingInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadHistory();
  proxySlider.addEventListener('input', updateProxyValue);
  updateProxyValue();
  
  window.electronAPI.onProgress((event, { percent, msg }) => {
    progressFill.style.width = `${percent}%`;
    progressMsg.textContent = msg || 'Currently jerking off Google\'s captcha';
  });
});

// Event Listeners
spawnButton.addEventListener('click', () => {
  accountForm.style.display = 'block';
  randomizeData();
});

randomizeButton.addEventListener('click', randomizeData);

createButton.addEventListener('click', async () => {
  const batchCount = parseInt(document.getElementById('batchCount').value);
  accountForm.style.display = 'none';
  progressSection.style.display = 'block';
  emailSection.style.display = 'block';
  resultSection.style.display = 'none';
  progressFill.style.width = '0%';
  
  for (let i = 0; i < batchCount; i += 3) { // Parallel 3 at a time
    const batch = [];
    for (let j = 0; j < 3 && (i + j) < batchCount; j++) {
      randomizeData();
      const accountData = {
        name: document.getElementById('fakeName').value,
        birthYear: document.getElementById('fakeBirthYear').value,
        birthplace: document.getElementById('fakeBirthplace').value,
        proxyDepth: parseInt(proxySlider.value),
        autoBuyNumber: numberToggle.checked,
        headless: headlessToggle.checked,
        tempEmail: tempEmail // Reuse or regenerate per batch if needed
      };
      batch.push(window.electronAPI.createAccount(accountData));
    }
    
    try {
      const results = await Promise.all(batch);
      results.forEach(result => {
        showSuccess(result);
      });
    } catch (error) {
      showFailure(error.message);
    }
  }
});

copyCredsButton.addEventListener('click', () => {
  navigator.clipboard.writeText(`Username: ${successUsername.textContent}\nPassword: ${successPassword.textContent}`);
  alert('Creds copied!');
});

exportSingleButton.addEventListener('click', () => {
  exportToCSV([currentAccount], 'single_account.csv');
});

retryButton.addEventListener('click', () => {
  resultSection.style.display = 'none';
  accountForm.style.display = 'block';
});

cryButton.addEventListener('click', () => {
  resultSection.style.display = 'none';
  alert('Boo hoo, try again pussy!');
});

nukeButton.addEventListener('click', () => {
  if (confirm('This will nuke everything—logs, DB, existence. Proceed?')) {
    window.electronAPI.nukeData().then(() => {
      historyCards.innerHTML = '';
      historySection.style.display = 'none';
      alert('Nuked! You never existed.');
    });
  }
});

exportAllButton.addEventListener('click', () => {
  exportToCSV(accountHistory, 'all_accounts.csv');
});

// Functions
function randomizeData() {
  const names = [
    'Chad Thundercock', 'Brock Hardwood', 'Dick Hammer', 'Rod Johnson',
    'Mike Hunt', 'Ben Dover', 'Hugh Jass', 'Dixie Normous',
    'Ivana Tinkle', 'Anita Bath', 'Seymour Butts', 'Phil McCracken'
  ];
  
  const places = [
    'Mid-Orgy, Nevada', 'Cum Valley, California', 'Dick City, Texas',
    'Pound Town, Florida', 'Bonerville, Alabama', 'Thrustville, Ohio',
    'Sperm Springs, Arizona', 'Climax, Colorado', 'Ejaculate, Montana',
    'Orgasm, Oregon', 'Pleasure Peak, Utah', 'Satisfaction, Wyoming'
  ];
  
  document.getElementById('fakeName').value = names[Math.floor(Math.random() * names.length)];
  document.getElementById('fakeBirthYear').value = Math.floor(Math.random() * 30) + 1985;
  document.getElementById('fakeBirthplace').value = places[Math.floor(Math.random() * places.length)];
}

function updateProxyValue() {
  const value = proxySlider.value;
  const labels = ['Baby', 'Weak', 'Decent', 'Good', 'Strong', 'Powerful', 'Epic', 'Legendary', 'Mythic', 'Godlike', 'Satan'];
  proxyValue.textContent = `Current: ${value} (${labels[value]})`;
}

function startEmailPolling() {
  if (pollingInterval) clearInterval(pollingInterval);
  
  pollingInterval = setInterval(async () => {
    try {
      if (!mailClient) {
        mailClient = new Mailjs();
        await mailClient.createOneAccount();
        tempEmail = mailClient.getAccount().address;
      }
      
      const messages = await mailClient.getMessageList();
      emailInbox.innerHTML = '';
      
      messages.forEach(msg => {
        const emailDiv = document.createElement('div');
        emailDiv.className = 'email';
        emailDiv.innerHTML = `
          <strong>From:</strong> ${msg.from}<br>
          <strong>Subject:</strong> ${msg.subject}<br>
          <strong>Date:</strong> ${new Date(msg.date).toLocaleString()}
        `;
        emailInbox.appendChild(emailDiv);
      });
    } catch (error) {
      console.error('Email polling error:', error);
    }
  }, 5000);
}

function showSuccess(account) {
  clearInterval(pollingInterval);
  progressSection.style.display = 'none';
  emailSection.style.display = 'none';
  resultSection.style.display = 'block';
  successCard.style.display = 'block';
  failureCard.style.display = 'none';
  
  successUsername.textContent = account.username;
  successPassword.textContent = account.password;
  
  // Auto-copy credentials
  navigator.clipboard.writeText(`Username: ${account.username}\nPassword: ${account.password}`);
  
  currentAccount = account;
  accountHistory.push(account);
  renderHistory();
  
  if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
}

function showFailure(error) {
  clearInterval(pollingInterval);
  progressSection.style.display = 'none';
  emailSection.style.display = 'none';
  resultSection.style.display = 'block';
  successCard.style.display = 'none';
  failureCard.style.display = 'block';
  
  console.error('Account creation failed:', error);
}

async function loadHistory() {
  try {
    accountHistory = await window.electronAPI.getHistory();
    renderHistory();
  } catch (error) {
    console.error('Failed to load history:', error);
  }
}

function renderHistory() {
  if (accountHistory.length === 0) {
    historySection.style.display = 'none';
    return;
  }
  
  historySection.style.display = 'block';
  historyCards.innerHTML = '';
  
  accountHistory.forEach((account, index) => {
    const card = document.createElement('div');
    card.className = 'history-card';
    card.innerHTML = `
      <div class="history-credentials">
        <div><strong>Username:</strong> ${account.username}</div>
        <div><strong>Password:</strong> ${account.password}</div>
        <div><strong>Name:</strong> ${account.name}</div>
        <div><strong>Created:</strong> ${new Date(account.createdAt).toLocaleString()}</div>
      </div>
      <div class="history-actions">
        <button class="history-button" onclick="copyHistory(${index})">COPY</button>
        <button class="history-button" onclick="deleteHistory(${index})">DELETE</button>
      </div>
    `;
    historyCards.appendChild(card);
  });
}

window.copyHistory = (index) => {
  const account = accountHistory[index];
  navigator.clipboard.writeText(`Username: ${account.username}\nPassword: ${account.password}`);
  alert('Credentials copied!');
};

window.deleteHistory = async (index) => {
  if (confirm('Delete this account from history?')) {
    accountHistory.splice(index, 1);
    renderHistory();
  }
};

function exportToCSV(accounts, filename) {
  let csv = 'Username,Password,Name,BirthYear,Birthplace,CreatedAt\n';
  accounts.forEach(account => {
    csv += `${account.username},${account.password},${account.name},${account.birthYear},${account.birthplace},${account.createdAt}\n`;
  });
  
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}