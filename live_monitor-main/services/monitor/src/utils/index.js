const { generateFingerprint } = require('./fingerprint');
const { sortData } = require('./sort');
const { filterData } = require('./filter');
const { paginate } = require('./pagination');

module.exports = {
  generateFingerprint,
  sortData,
  filterData,
  paginate
};

