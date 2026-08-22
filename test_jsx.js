const React = require('./frontend/node_modules/react');
const ReactDOMServer = require('./frontend/node_modules/react-dom/server');

const renderInjuries = (unavailable, nOut, keyOut, gkOut, teamName) => {
  if (unavailable) return React.createElement('span', { className: 'text-secondary' }, 'Injury Data Unavailable');
  if (nOut === 0) return React.createElement('span', { className: 'text-secondary' }, 'No injuries reported');
  const badges = [];
  if (keyOut) badges.push(React.createElement('span', { className: 'text-secondary', style: { fontWeight: 600 }, key: 'key' }, 'Player Unavailable'));
  if (gkOut) badges.push(React.createElement('span', { className: 'text-secondary', style: { fontWeight: 600 }, key: 'gk' }, 'GK Out'));
  return React.createElement(
    'span',
    null,
    React.createElement('strong', null, nOut + ' Out'),
    ' ',
    badges.length > 0 ? '(' + badges.map((b, i) => ReactDOMServer.renderToStaticMarkup(b)).join(', ') + ')' : ''
  );
};

console.log('--- RENDERED DOM OUTPUT ---');
console.log(ReactDOMServer.renderToStaticMarkup(renderInjuries(false, 2, true, false, 'Arsenal')));
console.log('--- END DOM OUTPUT ---');
