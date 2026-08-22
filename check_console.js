const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    
    try {
        await page.goto('http://127.0.0.1:5176/login', { waitUntil: 'networkidle2' });
        await page.type('#login-username', 'test');
        await page.type('#login-password', 'test');
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#login-submit-btn')
        ]);
        await page.goto('http://127.0.0.1:5176/league-insights', { waitUntil: 'networkidle2' });
        await new Promise(r => setTimeout(r, 2000));
    } catch(e) {
        console.error(e);
    }
    await browser.close();
    process.exit(0);
})();
