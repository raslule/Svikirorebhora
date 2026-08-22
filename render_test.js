const fs = require('fs');
const babel = require('@babel/core');
const React = require('./frontend/node_modules/react');
const ReactDOMServer = require('./frontend/node_modules/react-dom/server');

// Read the JSX file
const jsxCode = fs.readFileSync('frontend/src/components/PredictionPanel.jsx', 'utf-8');

// Transpile JSX to JS
const result = babel.transformSync(jsxCode, {
    presets: [['@babel/preset-react', { runtime: 'classic' }]]
});

// Mock dependencies
const mockToast = { error: () => {}, success: () => {} };
const mockApi = { bets: { create: async () => {} } };

// Create a function that executes the transpiled code
// We need to provide React and the mocks
const createComponent = new Function('React', 'toast', 'betsApi', `
    ${result.code.replace('import { useState } from \'react\';', 'const { useState } = React;')
                 .replace('import { bets as betsApi } from \'../api\';', '')
                 .replace('import toast from \'react-hot-toast\';', '')
                 .replace('export default function PredictionPanel', 'return function PredictionPanel')}
`);

const PredictionPanel = createComponent(React, mockToast, mockApi);

const mockProps = {
    fixture: { home_team: 'Arsenal', away_team: 'Man City', league: 'premier-league' },
    prediction: {
        meta: {
            home_injuries_unavailable: false,
            home_n_out: 2,
            home_miss_fw: true,
            home_miss_df: true,
            home_miss_mf: true,
            home_gk_out: true,
            
            away_injuries_unavailable: false,
            away_n_out: 0,
            away_miss_fw: false,
            away_miss_df: false,
            away_miss_mf: false,
            away_gk_out: false
        }
    },
    loading: false
};

const html = ReactDOMServer.renderToStaticMarkup(React.createElement(PredictionPanel, mockProps));

console.log("\n--- DOM OUTPUT ---");
// Extract the flex column gap 12 container where the injuries are rendered
const start = html.indexOf('<div style="display:flex;flex-direction:column;gap:12px;');
if (start !== -1) {
    const substr = html.substring(start, start + 1000);
    // Find the closing div of this block. For simplicity, just output the next 600 chars.
    console.log(substr);
} else {
    console.log(html);
}
console.log("--- END DOM OUTPUT ---\n");

