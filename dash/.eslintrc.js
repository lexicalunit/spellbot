module.exports = {
  extends: [
    'airbnb-typescript',
    'airbnb/hooks',
    'plugin:@typescript-eslint/recommended',
    'plugin:jest/recommended',
    'prettier',
    'prettier/react',
    'prettier/@typescript-eslint',
    'plugin:prettier/recommended'
  ],
  settings: {
    jest: { version: 26 }
  },
  plugins: ['react', '@typescript-eslint', 'jest'],
  env: {
    browser: true,
    es6: true,
    jest: true,
  },
  globals: {
    Atomics: 'readonly',
    SharedArrayBuffer: 'readonly',
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaFeatures: {
      jsx: true,
    },
    ecmaVersion: 2018,
    sourceType: 'module',
    project: `${__dirname}/tsconfig.json`,
  },
  rules: {
    'semi': ['error', 'never'],
    'linebreak-style': 'off',
    'no-param-reassign': ['error', { 'props': false }],
    'prettier/prettier': ['error', {
      endOfLine: 'auto',
      'semi': false,
    }],
  },
}
