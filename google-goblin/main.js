const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const accountCreator = require('./accountCreator');
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: path.join(__dirname, 'assets/icon.png')
  });
  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  accountCreator.nukeData(); // Auto-nuke on close
});

// IPC handlers (added progress send)
ipcMain.handle('create-account', async (event, accountData) => {
  return await accountCreator.createAccount(accountData, (percent, msg) => {
    event.sender.send('progress-update', { percent, msg });
  });
});

ipcMain.handle('get-history', async () => {
  return accountCreator.getHistory();
});

ipcMain.handle('export-history', async () => {
  return accountCreator.exportHistory();
});

ipcMain.handle('nuke-data', async () => {
  return accountCreator.nukeData();
});