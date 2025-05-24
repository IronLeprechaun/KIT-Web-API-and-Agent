# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default tseslint.config({
  extends: [
    // Remove ...tseslint.configs.recommended and replace with this
    ...tseslint.configs.recommendedTypeChecked,
    // Alternatively, use this for stricter rules
    ...tseslint.configs.strictTypeChecked,
    // Optionally, add this for stylistic rules
    ...tseslint.configs.stylisticTypeChecked,
  ],
  languageOptions: {
    // other options...
    parserOptions: {
      project: ['./tsconfig.node.json', './tsconfig.app.json'],
      tsconfigRootDir: import.meta.dirname,
    },
  },
})
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default tseslint.config({
  plugins: {
    // Add the react-x and react-dom plugins
    'react-x': reactX,
    'react-dom': reactDom,
  },
  rules: {
    // other rules...
    // Enable its recommended typescript rules
    ...reactX.configs['recommended-typescript'].rules,
    ...reactDom.configs.recommended.rules,
  },
})
```

## Testing

This project uses [Vitest](https://vitest.dev/) as the testing framework, along with [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) for component testing.

### Running Tests

-   **Run all tests once:**
    ```bash
    npm test
    # or
    npm run test
    ```

-   **Run tests in watch mode:**
    Vitest runs in watch mode by default.
    ```bash
    npm run test:watch
    # or simply
    npm test
    ```
    This will re-run tests when files change.

-   **Run tests with UI:**
    For a graphical interface to view and interact with your tests:
    ```bash
    npm run test:ui
    ```
    This will open the Vitest UI in your browser.

-   **Generate coverage report:**
    ```bash
    npm run coverage
    ```
    The coverage report will be generated in the `coverage/` directory.

### Test Setup

-   Test environment: `happy-dom` (configured in `vite.config.ts`)
-   Global test utilities (like `expect`, `describe`, `test`, `vi`) are available in test files (configured in `vite.config.ts`).
-   DOM-specific matchers from `@testing-library/jest-dom` are available via `vitest.setup.ts`.
-   TypeScript configuration for tests is in `tsconfig.vitest.json`.

### Writing Tests

-   Place test files (`*.test.ts` or `*.test.tsx`) alongside the files they test, or in a `__tests__` subdirectory.
-   Use React Testing Library utilities to render components and query the DOM.
-   Use `user-event` for simulating user interactions.