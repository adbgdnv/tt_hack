import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@alfalab/core-components-themes/corp.css';
import './styles.css';
import './print.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
