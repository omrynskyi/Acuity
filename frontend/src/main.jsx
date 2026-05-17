import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import './styles/global.css';
import './styles/design.css';
import heroImg from '../hero.jpg';

// Vite gives heroImg a hashed URL (e.g. /assets/hero-HASH.jpg).
// Set as CSS custom property before React renders so #bg-layer
// picks it up without a flash.
document.documentElement.style.setProperty('--hero-bg', `url(${heroImg})`);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
