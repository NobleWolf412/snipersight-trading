import numeral from 'numeral';

export const format = {
  number: (n: number, fmt = '0,0') => numeral(n).format(fmt),
  money: (n: number) => numeral(n).format('$0,0.00'),
  pct: (n: number, digits = 1) => `${numeral(n).format(`0.${'0'.repeat(digits)}`)}%`,
};
